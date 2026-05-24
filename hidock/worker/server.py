from __future__ import annotations

import json
import threading
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

from hidock.transcribers.util import log, payload_from_segments

if TYPE_CHECKING:
    from hidock.transcribers.base import Transcriber


class _WorkerState:
    lock: threading.Lock = threading.Lock()
    transcriber: Transcriber | None = None
    token: str | None = None


def _authorized(headers, token: str | None) -> bool:
    if not token:
        return True
    auth = headers.get("Authorization") or headers.get("authorization") or ""
    return auth == f"Bearer {token}"


def make_handler(state: _WorkerState) -> type[BaseHTTPRequestHandler]:
    class TranscribeHandler(BaseHTTPRequestHandler):
        server_version = "hidock-transcribe-worker/1.0"

        def log_message(self, fmt: str, *args) -> None:
            log(f"worker: {self.address_string()} - {fmt % args}")

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                body = json.dumps({"status": "ok"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/v1/transcribe":
                self.send_error(404)
                return

            if not _authorized(self.headers, state.token):
                self.send_error(401, "Unauthorized")
                return

            if state.transcriber is None:
                self.send_error(503, "Worker not ready")
                return

            if not state.lock.acquire(blocking=False):
                self.send_response(503)
                self.send_header("Retry-After", "30")
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Worker busy - one transcription at a time")
                return

            try:
                length = int(self.headers.get("Content-Length") or "0")
                raw = self.rfile.read(length)
                if not raw:
                    self.send_error(400, "Empty audio body")
                    return

                query = parse_qs(parsed.query)
                language = query.get("language", [None])[0]

                suffix = Path(self.headers.get("X-Filename") or "audio.mp3").suffix or ".mp3"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(raw)
                    tmp_path = Path(tmp.name)

                try:
                    log(f"worker: transcribing {tmp_path.name} ({len(raw) / 1024 / 1024:.1f} MB)...")
                    result = state.transcriber.transcribe(tmp_path)
                    payload = payload_from_segments(result.segments, result.duration_seconds)
                    body = json.dumps(payload).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    log("worker: transcription complete")
                finally:
                    tmp_path.unlink(missing_ok=True)
            finally:
                state.lock.release()

    return TranscribeHandler


def serve(
    *,
    host: str,
    port: int,
    transcriber: Transcriber,
    token: str | None = None,
) -> None:
    state = _WorkerState()
    state.transcriber = transcriber
    state.token = token

    handler = make_handler(state)
    server = ThreadingHTTPServer((host, port), handler)
    log(f"Transcribe worker listening on http://{host}:{port}")
    log("  POST /v1/transcribe  (raw audio body)")
    log("  GET  /health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Shutting down worker...")
    finally:
        transcriber.close()
        server.server_close()
