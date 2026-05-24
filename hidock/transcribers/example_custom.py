"""Example custom transcriber — copy and adapt for your own pipeline.

Enable in config.yaml:

    transcription:
      provider: custom
      custom_class: hidock.transcribers.example_custom.EchoTranscriber

Or point ``custom_class`` at any importable module on PYTHONPATH.
"""

from __future__ import annotations

from pathlib import Path

from hidock.config import Config
from hidock.markdown import TranscriptSegment
from hidock.transcribers.base import Transcriber, TranscriptionResult


class EchoTranscriber(Transcriber):
    """Stub that returns one segment — useful to verify the plugin wiring."""

    @classmethod
    def from_config(cls, config: Config) -> EchoTranscriber:
        return cls()

    @property
    def name(self) -> str:
        return "echo"

    def transcribe(self, audio_path: Path, *, reuse_cache: bool = False) -> TranscriptionResult:
        return TranscriptionResult(
            segments=[
                TranscriptSegment(
                    start=0.0,
                    end=1.0,
                    speaker="Speaker 1",
                    text=f"[custom stub] Would transcribe {audio_path.name}",
                ),
            ],
            duration_seconds=1.0,
        )
