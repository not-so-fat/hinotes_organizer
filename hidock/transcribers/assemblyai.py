from __future__ import annotations

import time
from pathlib import Path

import requests

from hidock.config import Config
from hidock.markdown import TranscriptSegment
from hidock.transcribers.base import Transcriber, TranscriptionResult
from hidock.transcribers.util import log, normalize_speaker_label

ASSEMBLYAI_BASE = "https://api.assemblyai.com/v2"
POLL_INTERVAL_SEC = 3
MAX_WAIT_SEC = 7200


class AssemblyAITranscriber(Transcriber):
    """Cloud transcription via AssemblyAI (transcript + speaker diarization)."""

    def __init__(self, api_key: str, *, language: str | None) -> None:
        self._api_key = api_key
        self._language = language
        self._headers = {"authorization": api_key}

    @classmethod
    def from_config(cls, config: Config) -> AssemblyAITranscriber:
        key = config.assemblyai_api_key()
        if not key:
            raise RuntimeError(
                "transcription.provider is assemblyai but secrets.assemblyai_api_key is not set.",
            )
        return cls(api_key=key, language=config.transcription.language)

    @property
    def name(self) -> str:
        return "assemblyai"

    def transcribe(self, audio_path: Path, *, reuse_cache: bool = False) -> TranscriptionResult:
        log(f"  AssemblyAI: uploading {audio_path.name}...")
        upload_url = self._upload(audio_path)
        transcript_id = self._create_transcript(upload_url)
        log(f"  AssemblyAI: transcribing (id {transcript_id})...")
        data = self._poll(transcript_id)
        segments, duration = self._parse_response(data)
        log(f"  AssemblyAI: done — {len(segments)} segment(s)")
        return TranscriptionResult(segments=segments, duration_seconds=duration)

    def _upload(self, audio_path: Path) -> str:
        with audio_path.open("rb") as handle:
            response = requests.post(
                f"{ASSEMBLYAI_BASE}/upload",
                headers=self._headers,
                data=handle,
                timeout=600,
            )
        response.raise_for_status()
        return response.json()["upload_url"]

    def _create_transcript(self, upload_url: str) -> str:
        body: dict[str, object] = {
            "audio_url": upload_url,
            "speaker_labels": True,
        }
        if self._language:
            body["language_code"] = self._language

        response = requests.post(
            f"{ASSEMBLYAI_BASE}/transcript",
            headers={**self._headers, "content-type": "application/json"},
            json=body,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["id"]

    def _poll(self, transcript_id: str) -> dict:
        started = time.time()
        while True:
            response = requests.get(
                f"{ASSEMBLYAI_BASE}/transcript/{transcript_id}",
                headers=self._headers,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            status = data.get("status")
            if status == "completed":
                return data
            if status == "error":
                raise RuntimeError(data.get("error") or "AssemblyAI transcription failed")
            if time.time() - started > MAX_WAIT_SEC:
                raise TimeoutError(
                    f"AssemblyAI transcription timed out after {MAX_WAIT_SEC}s",
                )
            time.sleep(POLL_INTERVAL_SEC)

    def _parse_response(self, data: dict) -> tuple[list[TranscriptSegment], float | None]:
        segments: list[TranscriptSegment] = []
        for row in data.get("utterances") or []:
            text = (row.get("text") or "").strip()
            if not text:
                continue
            segments.append(
                TranscriptSegment(
                    start=float(row["start"]) / 1000.0,
                    end=float(row["end"]) / 1000.0,
                    speaker=normalize_speaker_label(str(row.get("speaker") or "A")),
                    text=text,
                ),
            )

        if not segments and data.get("text"):
            segments.append(
                TranscriptSegment(
                    start=0.0,
                    end=float(data.get("audio_duration") or 0) / 1000.0,
                    speaker="Speaker 1",
                    text=str(data["text"]).strip(),
                ),
            )

        duration_ms = data.get("audio_duration")
        duration = float(duration_ms) / 1000.0 if duration_ms else None
        return segments, duration
