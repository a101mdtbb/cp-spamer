#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/cp"

if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
fi

pip install -q -r "$SCRIPT_DIR/requirements.txt"

exec python3 "$SCRIPT_DIR/cp.py"
