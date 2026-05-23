from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from hidock.filename import ParsedRecording


@dataclass
class TranscriptSegment:
    start: float
    end: float
    speaker: str
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "speaker": self.speaker,
            "text": self.text,
        }


def write_transcript_markdown(
    path: Path,
    *,
    title: str,
    parsed: ParsedRecording,
    segments: list[TranscriptSegment],
    source: str,
    tags: list[str],
    duration_seconds: float | None,
    segments_json_path: Path | None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    front_matter: dict[str, Any] = {
        "title": title,
        "date": parsed.date_slash,
        "recorded_at": parsed.iso_datetime,
        "device_file": parsed.device_file,
        "signature": parsed.signature,
        "source": source,
        "tags": tags,
    }
    if duration_seconds is not None:
        front_matter["duration_seconds"] = round(duration_seconds, 1)
    if segments_json_path is not None:
        front_matter["segments_file"] = segments_json_path.name

    yaml_block = yaml.safe_dump(front_matter, sort_keys=False, allow_unicode=True).strip()
    lines = ["---", yaml_block, "---", "", "# Raw Transcript", ""]

    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        lines.append(f"{seg.speaker}: {text}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_segments_json(path: Path, segments: list[TranscriptSegment], parsed: ParsedRecording) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "device_file": parsed.device_file,
        "signature": parsed.signature,
        "recorded_at": parsed.iso_datetime,
        "segments": [seg.to_dict() for seg in segments],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
