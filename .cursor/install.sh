#!/usr/bin/env bash
# Idempotent dependency setup for the Doku-Agent Cloud Agent environment.
# Prepares the FastAPI backend (Python venv) and the Vite/React frontend.
set -eo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# The base image ships python3.12 + pip but not the venv module.
if ! python3 -m venv --help >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3.12-venv
fi

# Backend: virtualenv + pinned requirements.
cd "$repo_root/backend"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt
deactivate

# Frontend: npm dependencies from the committed lockfile.
cd "$repo_root/frontend"
npm ci
