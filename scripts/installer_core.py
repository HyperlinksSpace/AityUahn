"""Shared local-forge installer logic (Windows exe, install.ps1, install.sh)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


DEFAULT_REPO = "HyperlinksSpace/AityUahn"
DEFAULT_BRANCH = "main"


def info(msg: str) -> None:
    print(f"==> {msg}")


def warn(msg: str) -> None:
    print(f"!!> {msg}")


def find_python() -> list[str]:
    if shutil.which("py"):
        for flag in ("-3.12", "-3.11", "-3"):
            cmd = ["py", flag, "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                return ["py", flag]
            except subprocess.CalledProcessError:
                continue
    for name in ("python3.11", "python3", "python"):
        if not shutil.which(name):
            continue
        try:
            subprocess.run(
                [name, "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"],
                check=True,
                capture_output=True,
            )
            return [name]
        except subprocess.CalledProcessError:
            continue
    raise RuntimeError(
        "Python 3.11+ is required. Install from https://www.python.org/downloads/ "
        "(check 'Add python.exe to PATH')."
    )


def run_python(py: list[str], args: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(py + args, check=True, cwd=cwd)


def clone_or_update(install_dir: Path, repo: str, branch: str) -> None:
    zip_url = f"https://github.com/{repo}/archive/refs/heads/{branch}.zip"
    if (install_dir / ".git").is_dir():
        info(f"Updating existing install at {install_dir}")
        if shutil.which("git"):
            try:
                subprocess.run(
                    ["git", "-C", str(install_dir), "pull", "--ff-only", "origin", branch],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError:
                warn("git pull failed — continuing with existing files")
        return
    if install_dir.exists() and any(install_dir.iterdir()):
        raise RuntimeError(
            f"Install directory exists and is not empty: {install_dir} "
            f"(set AITYUAHN_INSTALL_DIR or remove it)"
        )
    install_dir.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("git"):
        info(f"Cloning https://github.com/{repo}.git → {install_dir}")
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch, f"https://github.com/{repo}.git", str(install_dir)],
            check=True,
        )
        return
    info(f"Downloading ZIP → {install_dir}")
    with tempfile.TemporaryDirectory(prefix="aityuahn-") as tmp:
        tmp_path = Path(tmp)
        zip_path = tmp_path / "aityuahn.zip"
        urllib.request.urlretrieve(zip_url, zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_path)
        extracted = next((p for p in tmp_path.iterdir() if p.is_dir() and p.name.startswith("AityUahn")), None)
        if not extracted:
            raise RuntimeError("Could not find extracted folder in ZIP")
        install_dir.mkdir(parents=True, exist_ok=True)
        for item in extracted.iterdir():
            dest = install_dir / item.name
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            shutil.move(str(item), str(dest))


def setup_venv(py: list[str], install_dir: Path) -> None:
    venv = install_dir / ".venv"
    info(f"Creating virtualenv in {venv}")
    run_python(py, ["-m", "venv", str(venv)])
    if sys.platform == "win32":
        pip_py = venv / "Scripts" / "python.exe"
    else:
        pip_py = venv / "bin" / "python"
    subprocess.run([str(pip_py), "-m", "pip", "install", "-U", "pip", "wheel"], check=True)
    subprocess.run([str(pip_py), "-m", "pip", "install", "-e", ".[dev]"], check=True, cwd=install_dir)


def write_config(install_dir: Path) -> None:
    example = install_dir / "config" / "forge.example.yaml"
    forge = install_dir / "forge.yaml"
    env_example = install_dir / ".env.example"
    env_file = install_dir / ".env"
    if not forge.is_file() and example.is_file():
        shutil.copy2(example, forge)
        info("Created forge.yaml from example")
    if not env_file.is_file() and env_example.is_file():
        shutil.copy2(env_example, env_file)
        info("Created .env from example — add API keys when ready")


def write_launchers(install_dir: Path) -> None:
    serve_bat = install_dir / "serve.bat"
    serve_bat.write_text(
        '@echo off\r\n'
        'cd /d "%~dp0"\r\n'
        'call "%~dp0.venv\\Scripts\\activate.bat"\r\n'
        'aityuahn serve %*\r\n',
        encoding="ascii",
    )
    serve_sh = install_dir / "serve.sh"
    serve_sh.write_text(
        '#!/usr/bin/env sh\n'
        'cd "$(dirname "$0")"\n'
        '. .venv/bin/activate 2>/dev/null || . .venv/Scripts/activate\n'
        'exec aityuahn serve "$@"\n',
        encoding="utf-8",
    )
    info("Launchers: serve.bat and serve.sh")


def run_install(
    install_dir: Path | None = None,
    *,
    repo: str | None = None,
    branch: str | None = None,
) -> Path:
    target = install_dir or Path(os.environ.get("AITYUAHN_INSTALL_DIR", Path.home() / "AityUahn"))
    repo = repo or os.environ.get("AITYUAHN_REPO", DEFAULT_REPO)
    branch = branch or os.environ.get("AITYUAHN_BRANCH", DEFAULT_BRANCH)
    info("AityUahn local forge installer")
    py = find_python()
    info(f"Using Python: {' '.join(py)}")
    clone_or_update(target, repo, branch)
    setup_venv(py, target)
    write_config(target)
    write_launchers(target)
    info(f"Done. Installed to: {target}")
    print(
        f"\nNext steps:\n"
        f"  cd \"{target}\"\n"
        f"  serve.bat          # Windows\n"
        f"  aityuahn serve     # after activating .venv\n"
        f"  Open http://127.0.0.1:8765 and connect the controller.\n"
    )
    return target
