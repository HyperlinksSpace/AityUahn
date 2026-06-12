# Local forge installer — GitHub Releases

Automatic Windows `.exe` builds (same idea as [HyperlinksSpaceProgram](https://github.com/HyperlinksSpace/HyperlinksSpaceProgram) electron releases).

## Download links (for users)

| What | URL |
|------|-----|
| **Latest installer** | https://github.com/HyperlinksSpace/AityUahn/releases/latest/download/aityuahn-installer.exe |
| **Releases page** | https://github.com/HyperlinksSpace/AityUahn/releases |
| **ZIP (main branch)** | https://github.com/HyperlinksSpace/AityUahn/archive/refs/heads/main.zip |

The UI reads these from `python/static/config.json` (`backendExe`, `backendRelease`).

## Automatic release on push

Workflow: **`.github/workflows/release-installer.yml`**

Triggers on push to `main` when paths change:

- `python/**`, `scripts/**`, `pyproject.toml`, `config/**`, `saas.yaml`

Or run manually: **Actions → Windows installer release → Run workflow**

Each run:

1. Builds `aityuahn-installer.exe` with PyInstaller on `windows-latest`
2. Creates tag `v{version}-build.{run_number}` (from `pyproject.toml` version)
3. Uploads `aityuahn-installer.exe` to GitHub Releases
4. Marks release as **Latest** → stable URL above always works

## What the exe does

1. Requires **Python 3.11+** on the user's PC (does not bundle Python)
2. Clones or updates `%USERPROFILE%\AityUahn`
3. Creates `.venv`, runs `pip install -e ".[dev]"`
4. Writes `forge.yaml`, `.env`, `serve.bat`

Then the user runs `serve.bat` and opens http://127.0.0.1:8765

## Build locally (maintainers)

```bash
pip install -e ".[installer]"
python scripts/build_installer.py
# → dist/aityuahn-installer.exe
```

## config.json (UI buttons)

```json
{
  "backendExe": "https://github.com/HyperlinksSpace/AityUahn/releases/latest/download/aityuahn-installer.exe",
  "backendRelease": "https://github.com/HyperlinksSpace/AityUahn/releases/latest"
}
```

After changing config, rebuild GitHub Pages: `python scripts/build_pages.py`

## Permissions

The workflow needs `contents: write` to create releases (uses `GITHUB_TOKEN`).

No extra secrets required for basic exe releases.
