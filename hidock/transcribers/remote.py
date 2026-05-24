from __future__ import annotations

import time
from pathlib import Path

import requests

from hidock.config import Config
from hidock.transcribers.base import Transcriber, TranscriptionResult
from hidock.transcribers.util import log, segments_from_payload

MAX_RETRIES = 30
RETRY_SLEEP_SEC = 10
REQUEST_TIMEOUT_SEC = 7200


class RemoteTranscriber(Transcriber):
    """POST audio to a self-hosted transcribe worker."""

    def __init__(self, remote_url: str, *, remote_token: str | None, language: str | None) -> None:
        self._remote_url = remote_url.rstrip("/")
        self._remote_token = (remote_token or "").strip() or None
        self._language = language

    @classmethod
    def from_config(cls, config: Config) -> RemoteTranscriber:
        url = (config.transcription.remote_url or "").strip()
        if not url:
            raise RuntimeError(
                "transcription.provider is remote but transcription.remote_url is not set.",
            )
        return cls(
            remote_url=url,
            remote_token=config.transcription.remote_token,
            language=config.transcription.language,
        )

    @property
    def name(self) -> str:
        return "remote"

    def transcribe(self, audio_path: Path, *, reuse_cache: bool = False) -> TranscriptionResult:
        url = f"{self._remote_url}/v1/transcribe"
        headers: dict[str, str] = {}
        if self._remote_token:
            headers["Authorization"] = f"Bearer {self._remote_token}"

        params: dict[str, str] = {}
        if self._language:
            params["language"] = self._language

        log(f"  Remote: uploading {audio_path.name} to {self._remote_url}...")

        for attempt in range(1, MAX_RETRIES + 1):
            with audio_path.open("rb") as handle:
                response = requests.post(
                    url,
                    headers=headers,
                    params=params,
                    data=handle,
                    timeout=REQUEST_TIMEOUT_SEC,
                )

            if response.status_code == 503:
                retry_after = int(response.headers.get("Retry-After", RETRY_SLEEP_SEC))
                log(
                    f"  Remote: worker busy (503), retry {attempt}/{MAX_RETRIES} "
                    f"in {retry_after}s...",
                )
                time.sleep(retry_after)
                continue

            if response.status_code >= 400:
                detail = response.text.strip() or response.reason
                raise RuntimeError(f"Remote transcriber failed ({response.status_code}): {detail}")

            payload = response.json()
            segments, duration = segments_from_payload(payload)
            log(f"  Remote: done — {len(segments)} segment(s)")
            return TranscriptionResult(segments=segments, duration_seconds=duration)

        raise RuntimeError("Remote transcriber failed: worker busy after maximum retries")
