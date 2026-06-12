#!/usr/bin/env bash
set -euo pipefail

REPO="$PWD"
if [[ ! -d "$REPO/.venv" ]]; then
  (cd "$REPO" && uv venv)
fi
# shellcheck disable=SC1091
source "$REPO/.venv/bin/activate"
python -m pip install --upgrade pip
pip install -r "$REPO/requirements.txt"
