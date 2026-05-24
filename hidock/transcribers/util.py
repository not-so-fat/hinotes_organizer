from __future__ import annotations

import sys
from typing import Any

from hidock.markdown import TranscriptSegment


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def normalize_speaker_label(raw: str) -> str:
    speaker = (raw or "").strip()
    if not speaker:
        return "Speaker 1"
    if speaker.startswith("Speaker "):
        return speaker
    if len(speaker) == 1 and speaker.isalpha():
        return f"Speaker {ord(speaker.upper()) - ord('A') + 1}"
    if speaker.startswith("SPEAKER_"):
        num = speaker.removeprefix("SPEAKER_").lstrip("0") or "0"
        return f"Speaker {int(num) + 1}"
    return f"Speaker {speaker}"


def segments_from_payload(payload: dict[str, Any]) -> tuple[list[TranscriptSegment], float | None]:
    rows = payload.get("segments") or []
    segments: list[TranscriptSegment] = []
    for row in rows:
        text = (row.get("text") or "").strip()
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                start=float(row["start"]),
                end=float(row["end"]),
                speaker=normalize_speaker_label(str(row.get("speaker") or "Speaker 1")),
                text=text,
            ),
        )
    duration = payload.get("duration_seconds")
    return segments, float(duration) if duration is not None else None


def payload_from_segments(
    segments: list[TranscriptSegment],
    duration_seconds: float | None,
) -> dict[str, Any]:
    return {
        "duration_seconds": duration_seconds,
        "segments": [seg.to_dict() for seg in segments],
    }
