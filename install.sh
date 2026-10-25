#!/usr/bin/env bash
# bilibili-favorites-brief skill installer (macOS / Linux)
#
# Usage:
#   ./install.sh --project-root /path/to/bili-brief
#   ./install.sh --target codex --project-root /path/to/bili-brief --force
#   ./install.sh --target custom --target-dir /my/skills --project-root /path/to/bili-brief
set -euo pipefail

SKILL_NAME="bilibili-favorites-brief"
TARGET="both"
TARGET_DIR=""
PROJECT_ROOT=""
BACKEND_URL="http://127.0.0.1:8483"
OUTPUT_ROOT=""
PYTHON_BIN=""
PROVIDER_ID="deepseek"
MODEL_NAME="deepseek-chat"
FORCE=0

usage() {
    grep '^#' "$0" | sed 's/^# \{0,1\}//' | head -8
    exit 1
}

while [ $# -gt 0 ]; do
    case "$1" in
        --target) TARGET="$2"; shift 2 ;;
        --target-dir) TARGET_DIR="$2"; shift 2 ;;
        --project-root) PROJECT_ROOT="$2"; shift 2 ;;
        --backend-url) BACKEND_URL="$2"; shift 2 ;;
        --output-root) OUTPUT_ROOT="$2"; shift 2 ;;
        --python) PYTHON_BIN="$2"; shift 2 ;;
        --provider) PROVIDER_ID="$2"; shift 2 ;;
        --model) MODEL_NAME="$2"; shift 2 ;;
        --force) FORCE=1; shift ;;
        -h|--help) usage ;;
        *) echo "Unknown argument: $1" >&2; usage ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$SCRIPT_DIR/$SKILL_NAME"

step() { printf '==> %s\n' "$1"; }
ok()   { printf '    OK   %s\n' "$1"; }
warn() { printf '    WARN %s\n' "$1"; }

step "Checking package contents"
[ -f "$SOURCE/SKILL.md" ] || { echo "SKILL.md missing under $SOURCE"; exit 1; }
[ -f "$SOURCE/scripts/bili_favorites.py" ] || { echo "scripts missing"; exit 1; }
ok "package layout verified"

if [ -z "$PROJECT_ROOT" ]; then
    read -r -p "Path to the bili-brief project root: " PROJECT_ROOT
fi
[ -n "$PROJECT_ROOT" ] || { echo "project root is required"; exit 1; }
PROJECT_ROOT="${PROJECT_ROOT%/}"

if [ -z "$OUTPUT_ROOT" ]; then
    OUTPUT_ROOT="$HOME/Documents/BiliBrief"
fi

if [ -z "$PYTHON_BIN" ]; then
    if [ -x "$PROJECT_ROOT/backend/.venv/bin/python" ]; then
        PYTHON_BIN="$PROJECT_ROOT/backend/.venv/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python3)"
    fi
fi

step "Resolving skill target directories"
TARGETS=()
case "$TARGET" in
    workbuddy) TARGETS=("WorkBuddy|$HOME/.workbuddy/skills") ;;
    codex) TARGETS=("Codex|$HOME/.codex/skills") ;;
    both) TARGETS=("WorkBuddy|$HOME/.workbuddy/skills" "Codex|$HOME/.codex/skills") ;;
    custom)
        [ -n "$TARGET_DIR" ] || { echo "--target-dir required with --target custom"; exit 1; }
        TARGETS=("Custom|$TARGET_DIR") ;;
    *) echo "Invalid --target: $TARGET"; exit 1 ;;
esac
for entry in "${TARGETS[@]}"; do ok "${entry%%|*}: ${entry##*|}"; done

step "Installing skill files"
INSTALLED=()
for entry in "${TARGETS[@]}"; do
    label="${entry%%|*}"
    root="${entry##*|}"
    mkdir -p "$root"
    dest="$root/$SKILL_NAME"
    if [ -e "$dest" ]; then
        if [ "$FORCE" -eq 1 ]; then
            rm -rf "$dest"
            ok "$label existing copy replaced"
        else
            backup="$dest.bak-$(date +%Y%m%d-%H%M%S)"
            mv "$dest" "$backup"
            warn "$label existing copy moved to $backup"
        fi
    fi
    cp -R "$SOURCE" "$root/"
    find "$dest" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
    INSTALLED+=("$dest")
    ok "$label installed to $dest"
done

step "Writing config.json"
CONFIG_JSON=$(cat <<EOF
{
  "project_root": "$PROJECT_ROOT",
  "backend_url": "$BACKEND_URL",
  "output_root": "$OUTPUT_ROOT",
  "provider_id": "$PROVIDER_ID",
  "model_name": "$MODEL_NAME"
}
EOF
)
for dest in "${INSTALLED[@]}"; do
    printf '%s\n' "$CONFIG_JSON" > "$dest/config.json"
    ok "$dest/config.json"
done

step "Verifying runtime"
if [ -n "$PYTHON_BIN" ] && [ -x "$PYTHON_BIN" ]; then
    if "$PYTHON_BIN" -c "import markdown" >/dev/null 2>&1; then
        ok "python: $PYTHON_BIN (markdown available)"
    else
        warn "$PYTHON_BIN lacks 'markdown'. Run: $PYTHON_BIN -m pip install markdown"
    fi
    if "$PYTHON_BIN" "${INSTALLED[0]}/scripts/bili_favorites.py" --help >/dev/null 2>&1; then
        ok "bili_favorites.py CLI loads"
    else
        warn "bili_favorites.py failed to load"
    fi
else
    warn "no usable python interpreter found"
fi

if command -v curl >/dev/null 2>&1; then
    code=$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$BACKEND_URL" || true)
    if [ -n "$code" ] && [ "$code" != "000" ]; then
        ok "backend $BACKEND_URL responding (HTTP $code)"
    else
        warn "backend $BACKEND_URL not reachable. Start BiliBrief backend before using the skill."
    fi
fi

printf '\nDone. Installed to:\n'
for p in "${INSTALLED[@]}"; do printf '  %s\n' "$p"; done
printf '\nNext steps:\n'
printf '  1. Restart the agent app so the skill is discovered.\n'
printf '  2. Make sure the BiliBrief backend is running at %s\n' "$BACKEND_URL"
printf '  3. Smoke test: "%s" "%s" --config "%s" list\n\n' "$PYTHON_BIN" "${INSTALLED[0]}/scripts/bili_favorites.py" "${INSTALLED[0]}/config.json"
