#!/usr/bin/env bash
# BiliBrief server deployment (macOS / Linux)
#
# Usage:
#   ./deploy.sh                 # create venv, install deps, prepare .env
#   ./deploy.sh --start         # ... then start the backend
#   ./deploy.sh --recreate      # rebuild the venv from scratch
#   ./deploy.sh --build-frontend
set -euo pipefail

SERVER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/server"
PYTHON_BIN=""
RECREATE=0
BUILD_FRONTEND=0
START=0
SKIP_INSTALL=0

while [ $# -gt 0 ]; do
    case "$1" in
        --server) SERVER_DIR="$2"; shift 2 ;;
        --python) PYTHON_BIN="$2"; shift 2 ;;
        --recreate) RECREATE=1; shift ;;
        --build-frontend) BUILD_FRONTEND=1; shift ;;
        --start) START=1; shift ;;
        --skip-install) SKIP_INSTALL=1; shift ;;
        -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

step() { printf '==> %s\n' "$1"; }
ok()   { printf '    OK   %s\n' "$1"; }
warn() { printf '    WARN %s\n' "$1"; }

BACKEND_DIR="$SERVER_DIR/backend"
VENV_DIR="$BACKEND_DIR/.venv"
VENV_PY="$VENV_DIR/bin/python"
REQUIREMENTS="$BACKEND_DIR/requirements.txt"

step "Checking server snapshot"
[ -f "$REQUIREMENTS" ] || { echo "requirements.txt not found at $REQUIREMENTS"; exit 1; }
ok "server: $SERVER_DIR"

step "Resolving Python 3.10+"
if [ -z "$PYTHON_BIN" ]; then
    for candidate in python3.12 python3.11 python3.10 python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            ver=$("$candidate" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "0.0")
            major="${ver%%.*}"; minor="${ver##*.}"
            if [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; then PYTHON_BIN="$(command -v "$candidate")"; break; fi
        fi
    done
fi
[ -n "$PYTHON_BIN" ] || { echo "Python 3.10+ not found. Install it or pass --python /path/to/python3."; exit 1; }
ok "python: $PYTHON_BIN ($("$PYTHON_BIN" -c 'import sys;print(sys.version.split()[0])'))"

step "Preparing virtual environment"
if [ "$RECREATE" -eq 1 ] && [ -d "$VENV_DIR" ]; then rm -rf "$VENV_DIR"; ok "old venv removed"; fi
if [ ! -x "$VENV_PY" ]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    ok "venv created: $VENV_DIR"
else
    ok "venv already present"
fi

if [ "$SKIP_INSTALL" -eq 0 ]; then
    step "Installing Python dependencies (this takes several minutes)"
    "$VENV_PY" -m pip install --upgrade pip --quiet
    "$VENV_PY" -m pip install -r "$REQUIREMENTS"
    ok "dependencies installed"
else
    warn "dependency install skipped"
fi

step "Configuring backend .env"
ENV_FILE="$BACKEND_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    ok ".env already exists (left untouched)"
elif [ -f "$BACKEND_DIR/.env.example" ]; then
    cp "$BACKEND_DIR/.env.example" "$ENV_FILE"
    ok ".env created from .env.example -> $ENV_FILE"
else
    warn ".env.example missing, skipped"
fi

step "Checking ffmpeg"
FFMPEG_OK=0
if command -v ffmpeg >/dev/null 2>&1; then FFMPEG_OK=1; ok "ffmpeg on PATH: $(command -v ffmpeg)"; fi
if [ "$FFMPEG_OK" -eq 0 ] && [ -x "$BACKEND_DIR/tools/ffmpeg/ffmpeg" ]; then FFMPEG_OK=1; ok "bundled ffmpeg: $BACKEND_DIR/tools/ffmpeg"; fi
if [ "$FFMPEG_OK" -eq 0 ]; then
    warn "ffmpeg not found. Install it (brew install ffmpeg / apt install ffmpeg) or set FFMPEG_BIN_PATH in $ENV_FILE"
fi

step "Frontend"
if [ "$BUILD_FRONTEND" -eq 1 ]; then
    if command -v npm >/dev/null 2>&1; then
        cd "$SERVER_DIR/BillNote_frontend"
        if command -v pnpm >/dev/null 2>&1 && [ -f pnpm-lock.yaml ]; then pnpm install && pnpm run build; else npm install && npm run build; fi
        ok "frontend built"
    else
        warn "npm not found; keeping existing dist"
    fi
elif [ -f "$SERVER_DIR/BillNote_frontend/dist/index.html" ]; then
    ok "prebuilt frontend present: $SERVER_DIR/BillNote_frontend/dist"
else
    warn "no prebuilt dist; pass --build-frontend on a machine with Node.js"
fi

step "Summary"
printf '    python : %s\n    backend: %s\n    .env   : %s\n\n' "$VENV_PY" "$BACKEND_DIR" "$ENV_FILE"
printf 'Next steps:\n'
printf '  1. Start backend:  (cd "%s" && "%s" main.py)   default http://127.0.0.1:8483\n' "$BACKEND_DIR" "$VENV_PY"
printf '  2. Open the UI, sign in to Bilibili, save the model API key in Settings.\n'
printf '  3. Install the skill:  ./install.sh --project-root "%s"\n\n' "$SERVER_DIR"

if [ "$START" -eq 1 ]; then
    step "Starting backend (Ctrl+C to stop)"
    cd "$BACKEND_DIR" && exec "$VENV_PY" main.py
fi
