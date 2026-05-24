"""Legacy module — transcription lives in hidock.transcribers."""

from hidock.transcribers.local import (
    load_whisper_cache,
    save_whisper_cache,
    whisper_cache_path,
)

__all__ = ["load_whisper_cache", "save_whisper_cache", "whisper_cache_path"]
