from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class FileRecord:
    signature: str
    device_file: str
    recorded_at: str | None = None
    downloaded_at: str | None = None
    audio_path: str | None = None
    transcribed_at: str | None = None
    markdown_path: str | None = None
    segments_path: str | None = None


@dataclass
class PipelineState:
    files: dict[str, FileRecord] = field(default_factory=dict)

    def get(self, signature: str) -> FileRecord | None:
        return self.files.get(signature)

    def upsert(self, record: FileRecord) -> None:
        self.files[record.signature] = record

    def is_downloaded(self, signature: str) -> bool:
        rec = self.get(signature)
        return rec is not None and rec.audio_path is not None

    def is_transcribed(self, signature: str) -> bool:
        rec = self.get(signature)
        return rec is not None and rec.markdown_path is not None


def load_state(path: Path) -> PipelineState:
    if not path.exists():
        return PipelineState()
    data = json.loads(path.read_text())
    files = {
        sig: FileRecord(**rec) for sig, rec in (data.get("files") or {}).items()
    }
    return PipelineState(files=files)


def save_state(path: Path, state: PipelineState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"files": {sig: asdict(rec) for sig, rec in state.files.items()}}
    path.write_text(json.dumps(payload, indent=2) + "\n")
