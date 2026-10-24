#!/usr/bin/env bash
# Starts JARVIS: the Python brain and the web interface. Stop with Ctrl+C.
set -e
cd "$(dirname "$0")"

# Prefer a newer Python (the Gemma 4 model needs 3.10+); fall back to the Mac's own python3.
PY=python3
for cand in python3.13 python3.12 python3.11 python3.10 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then PY="$cand"; break; fi
done
echo "Using $($PY --version) ($PY)"

# A .venv built on an old Python is rebuilt when a newer one is available.
if [ -d .venv ] && [ "$PY" != python3 ] && ! .venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
  echo "Rebuilding the Python environment on the newer Python..."
  rm -rf .venv
fi

if [ ! -d .venv ]; then
  echo "First run: creating the Python environment (a few minutes)..."
  "$PY" -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r backend/requirements.txt
fi
if [ ! -d frontend/jarvis-ui/node_modules ]; then
  echo "First run: installing the interface..."
  (cd frontend/jarvis-ui && npm install)
fi

.venv/bin/python backend/server.py &
BRAIN=$!
trap 'kill $BRAIN 2>/dev/null' EXIT INT TERM
cd frontend/jarvis-ui && npm run dev -- --open
