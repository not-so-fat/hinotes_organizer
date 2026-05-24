from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from hidock.markdown import TranscriptSegment

if TYPE_CHECKING:
    from hidock.config import Config


@dataclass(frozen=True)
class TranscriptionResult:
    """Normalized output every transcriber must produce."""

    segments: list[TranscriptSegment]
    duration_seconds: float | None = None


class Transcriber(ABC):
    """Pluggable transcription backend.

    Implement ``from_config`` and ``transcribe``. Optionally override ``prepare``,
    ``close``, and ``supports_cache_reuse`` for batch setup or caching.

    Custom backends: set ``transcription.provider: custom`` and
    ``transcription.custom_class: my_module.MyTranscriber`` in config.yaml.
    """

    @classmethod
    @abstractmethod
    def from_config(cls, config: Config) -> Transcriber:
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    def prepare(self, audio_paths: list[Path], *, reuse_cache: bool = False) -> None:
        """Load models or warm up before processing a batch."""

    def close(self) -> None:
        """Release resources after a batch."""

    @abstractmethod
    def transcribe(self, audio_path: Path, *, reuse_cache: bool = False) -> TranscriptionResult:
        raise NotImplementedError

    def supports_cache_reuse(self) -> bool:
        return False
