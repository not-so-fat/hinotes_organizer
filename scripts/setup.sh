#!/usr/bin/env bash
# One-time setup for the default AssemblyAI workflow.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Python venv"
python3 -m venv .venv
# shellcheck source=/dev/null
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt

echo "==> USB sync (Node)"
if ! command -v node >/dev/null 2>&1; then
  echo "Node.js 22+ is required. Install from https://nodejs.org/ or: brew install node"
  exit 1
fi
(
  cd device_usb
  npm install
  npm run build
)

if [[ ! -f config.yaml ]]; then
  cp config.example.yaml config.yaml
  echo ""
  echo "Created config.yaml — edit these two fields before running:"
  echo "  1. output.dir"
  echo "  2. secrets.assemblyai_api_key  (https://www.assemblyai.com/dashboard)"
  echo ""
else
  echo "config.yaml already exists — left unchanged."
fi

echo ""
echo "Setup complete. Next:"
echo "  source .venv/bin/activate"
echo "  # close HiNotes / Chrome, plug in HiDock"
echo "  python scripts/pipeline.py run --limit 1"
