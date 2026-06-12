#!/usr/bin/env sh
# AityUahn backend installer — Git Bash, WSL, macOS, Linux
# Usage: curl -LsSf https://raw.githubusercontent.com/HyperlinksSpace/AityUahn/main/scripts/install.sh | sh
# Optional: AITYUAHN_INSTALL_DIR=~/projects/AityUahn sh

set -eu

REPO="${AITYUAHN_REPO:-HyperlinksSpace/AityUahn}"
BRANCH="${AITYUAHN_BRANCH:-main}"
INSTALL_DIR="${AITYUAHN_INSTALL_DIR:-$HOME/AityUahn}"
ZIP_URL="https://github.com/${REPO}/archive/refs/heads/${BRANCH}.zip"

info() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

find_python() {
  for cmd in python3.12 python3.11 python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
      if "$cmd" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
        echo "$cmd"
        return 0
      fi
    fi
  done
  if command -v py >/dev/null 2>&1; then
    for ver in 3.12 3.11 3; do
      if py "-$ver" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
        echo "py -$ver"
        return 0
      fi
    done
  fi
  return 1
}

clone_or_update() {
  if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating existing install at $INSTALL_DIR"
    git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH" || warn "git pull failed — continuing with existing files"
    return
  fi
  if [ -d "$INSTALL_DIR" ] && [ -n "$(ls -A "$INSTALL_DIR" 2>/dev/null || true)" ]; then
    die "Install directory exists and is not empty: $INSTALL_DIR (set AITYUAHN_INSTALL_DIR or remove it)"
  fi
  mkdir -p "$(dirname "$INSTALL_DIR")"
  if command -v git >/dev/null 2>&1; then
    info "Cloning https://github.com/${REPO}.git → $INSTALL_DIR"
    git clone --depth 1 --branch "$BRANCH" "https://github.com/${REPO}.git" "$INSTALL_DIR"
    return
  fi
  info "Downloading ZIP (git not found) → $INSTALL_DIR"
  tmp="$(mktemp -d 2>/dev/null || mktemp -d -t aityuahn)"
  trap 'rm -rf "$tmp"' EXIT INT TERM
  if command -v curl >/dev/null 2>&1; then
    curl -LsSf "$ZIP_URL" -o "$tmp/aityuahn.zip"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$tmp/aityuahn.zip" "$ZIP_URL"
  else
    die "Need git, curl, or wget to download AityUahn"
  fi
  mkdir -p "$INSTALL_DIR"
  if command -v unzip >/dev/null 2>&1; then
    unzip -q "$tmp/aityuahn.zip" -d "$tmp"
  elif command -v tar >/dev/null 2>&1; then
    (cd "$tmp" && tar -xf aityuahn.zip)
  else
    die "Need unzip or tar to extract the ZIP"
  fi
  extracted="$(find "$tmp" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  cp -R "$extracted"/. "$INSTALL_DIR"/
}

setup_venv() {
  PY="$1"
  info "Creating virtualenv in $INSTALL_DIR/.venv"
  # shellcheck disable=SC2086
  $PY -m venv "$INSTALL_DIR/.venv"
  # shellcheck disable=SC1091
  . "$INSTALL_DIR/.venv/bin/activate" 2>/dev/null || . "$INSTALL_DIR/.venv/Scripts/activate"
  python -m pip install -U pip wheel
  # Must run from project root — "$INSTALL_DIR/.[dev]" breaks pip on Windows/Git Bash
  (cd "$INSTALL_DIR" && pip install -e ".[dev]")
}

write_config() {
  cd "$INSTALL_DIR"
  if [ ! -f forge.yaml ] && [ -f config/forge.example.yaml ]; then
    cp config/forge.example.yaml forge.yaml
    info "Created forge.yaml from example"
  fi
  if [ ! -f .env ] && [ -f .env.example ]; then
    cp .env.example .env
    info "Created .env from example — add API keys when ready"
  fi
}

write_launcher() {
  cat >"$INSTALL_DIR/serve.sh" <<'EOF'
#!/usr/bin/env sh
cd "$(dirname "$0")"
. .venv/bin/activate 2>/dev/null || . .venv/Scripts/activate
exec aityuahn serve "$@"
EOF
  chmod +x "$INSTALL_DIR/serve.sh"
}

main() {
  info "AityUahn backend installer"
  PY="$(find_python)" || die "Python 3.11+ is required. Install from https://www.python.org/downloads/"
  info "Using Python: $PY"
  clone_or_update
  setup_venv "$PY"
  write_config
  write_launcher
  info "Done. Installed to: $INSTALL_DIR"
  printf '\nNext steps:\n'
  printf '  cd "%s"\n' "$INSTALL_DIR"
  printf '  source .venv/bin/activate   # or: source .venv/Scripts/activate on Windows Git Bash\n'
  printf '  aityuahn serve\n'
  printf '  Open http://127.0.0.1:8765 and connect the controller.\n\n'
}

main "$@"
