#!/usr/bin/env bash
# Run sync + transcribe. Safe to call repeatedly (skips finished files).
# Exits quietly if HiDock is not connected or a run is already in progress.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! ioreg -p IOUSB -l -w 0 2>/dev/null | grep -qiE '"idVendor"\s*=\s*(4310|0x10d6)'; then
  exit 0
fi

exec 9>"${TMPDIR:-/tmp}/hidock-pipeline.lock"
if ! flock -n 9; then
  exit 0
fi

# shellcheck source=/dev/null
source "$ROOT/.venv/bin/activate"
exec python "$ROOT/scripts/pipeline.py" run "$@"
