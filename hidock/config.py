from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class OutputConfig:
    dir: Path
    filename_pattern: str


@dataclass
class AudioConfig:
    cache_dir: Path


@dataclass
class SyncConfig:
    include_wip: bool
    delete_after_download: bool
    delete_after_transcribe: bool


@dataclass
class TranscriptionConfig:
    provider: str
    model: str
    device: str
    compute_type: str
    language: str | None
    diarize: bool
    custom_class: str | None
    remote_url: str | None
    remote_token: str | None


@dataclass
class SecretsConfig:
    hf_token: str | None
    hinotes_token: str | None
    assemblyai_api_key: str | None


@dataclass
class MarkdownConfig:
    title_template: str
    source: str
    tags: list[str]
    save_segments_json: bool


@dataclass
class Config:
    output: OutputConfig
    audio: AudioConfig
    sync: SyncConfig
    transcription: TranscriptionConfig
    markdown: MarkdownConfig
    secrets: SecretsConfig
    state_file: Path

    @property
    def transcript_dir(self) -> Path:
        return self.output.dir

    def hf_token(self) -> str | None:
        token = (self.secrets.hf_token or "").strip()
        return token or None

    def hinotes_token(self) -> str | None:
        token = (self.secrets.hinotes_token or "").strip()
        return token or None

    def assemblyai_api_key(self) -> str | None:
        token = (self.secrets.assemblyai_api_key or "").strip()
        return token or None


def _resolve_path(value: str | Path, base: Path = REPO_ROOT) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return path


def load_config(path: Path | None = None) -> Config:
    config_path = path or REPO_ROOT / "config.yaml"
    if not config_path.exists():
        example = REPO_ROOT / "config.example.yaml"
        raise FileNotFoundError(
            f"Missing {config_path}. Copy {example.name} to config.yaml and edit paths.",
        )

    raw: dict[str, Any] = yaml.safe_load(config_path.read_text()) or {}

    output = raw.get("output", {})
    audio = raw.get("audio", {})
    sync = raw.get("sync", {})
    transcription = raw.get("transcription", {})
    markdown = raw.get("markdown", {})
    secrets = raw.get("secrets", {})

    provider = (transcription.get("provider") or "local").strip().lower()
    delete_after_transcribe_raw = sync.get("delete_after_transcribe")
    if delete_after_transcribe_raw is None:
        delete_after_transcribe = provider in ("assemblyai", "remote")
    else:
        delete_after_transcribe = bool(delete_after_transcribe_raw)

    return Config(
        output=OutputConfig(
            dir=_resolve_path(output.get("dir", "./output/transcripts")),
            filename_pattern=output.get("filename_pattern", "{date}_{title}_{id}"),
        ),
        audio=AudioConfig(cache_dir=_resolve_path(audio.get("cache_dir", ".cache/audio"))),
        sync=SyncConfig(
            include_wip=bool(sync.get("include_wip", False)),
            delete_after_download=bool(sync.get("delete_after_download", False)),
            delete_after_transcribe=delete_after_transcribe,
        ),
        transcription=TranscriptionConfig(
            provider=provider,
            model=transcription.get("model", "medium"),
            device=transcription.get("device", "auto"),
            compute_type=transcription.get("compute_type", "default"),
            language=transcription.get("language"),
            diarize=bool(transcription.get("diarize", True)),
            custom_class=transcription.get("custom_class"),
            remote_url=transcription.get("remote_url"),
            remote_token=transcription.get("remote_token"),
        ),
        markdown=MarkdownConfig(
            title_template=markdown.get("title_template", "Recording {rec_id}"),
            source=markdown.get("source", "HiDock"),
            tags=list(markdown.get("tags", ["transcript", "hidock", "meeting"])),
            save_segments_json=bool(markdown.get("save_segments_json", True)),
        ),
        secrets=SecretsConfig(
            hf_token=secrets.get("hf_token"),
            hinotes_token=secrets.get("hinotes_token"),
            assemblyai_api_key=secrets.get("assemblyai_api_key"),
        ),
        state_file=_resolve_path(raw.get("state_file", ".state/pipeline.json")),
    )
