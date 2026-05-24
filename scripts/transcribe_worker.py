#!/usr/bin/env python3
"""Self-hosted transcription worker — runs local Whisper+pyannote on a GPU machine.

Requires local deps:
  pip install -r requirements-local.txt

Usage:
  python scripts/transcribe_worker.py --host 0.0.0.0 --port 8765

Point clients at:
  transcription:
    provider: remote
    remote_url: http://your-gpu-host:8765
    remote_token: "optional-shared-secret"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from hidock.config import load_config
from hidock.transcribers import get_transcriber
from hidock.worker.server import serve


def main() -> None:
    parser = argparse.ArgumentParser(description="HiDock self-hosted transcribe worker")
    parser.add_argument("--config", help="Path to config.yaml (default: ./config.yaml)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (use 0.0.0.0 for LAN)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--token",
        help="Bearer token required from clients (default: transcription.remote_token from config)",
    )
    args = parser.parse_args()

    config = load_config(Path(args.config) if args.config else None)
    if config.transcription.provider != "local":
        print(
            "Warning: worker always uses local transcriber; "
            f"config has provider={config.transcription.provider!r}",
            file=sys.stderr,
        )

    config.transcription.provider = "local"
    transcriber = get_transcriber(config)
    token = (args.token or config.transcription.remote_token or "").strip() or None

    serve(host=args.host, port=args.port, transcriber=transcriber, token=token)


if __name__ == "__main__":
    main()
