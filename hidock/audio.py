from __future__ import annotations

from pathlib import Path


def probe_audio_duration_seconds(audio_path: Path) -> float | None:
    """Return media duration in seconds from file metadata (not decode time)."""
    try:
        import av
    except ImportError:
        return None

    try:
        with av.open(str(audio_path)) as container:
            if container.duration:
                return float(container.duration) / 1_000_000.0

            audio_streams = [s for s in container.streams if s.type == "audio"]
            if not audio_streams:
                return None

            stream = audio_streams[0]
            if stream.duration is not None and stream.time_base:
                return float(stream.duration * stream.time_base)
    except OSError:
        return None

    return None
