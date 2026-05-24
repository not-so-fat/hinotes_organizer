from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hidock.config import Config
from hidock.markdown import TranscriptSegment
from hidock.transcribers.base import Transcriber, TranscriptionResult

DIARIZATION_MODEL = "pyannote/speaker-diarization-community-1"
DIARIZATION_SAMPLE_RATE = 16_000
WHISPER_CACHE_VERSION = 1


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _resolve_device(whisper_device: str) -> tuple[str, str]:
    if whisper_device != "auto":
        compute = "float16" if whisper_device == "cuda" else "int8"
        return whisper_device, compute

    try:
        import torch

        if torch.cuda.is_available():
            return "cuda", "float16"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "cpu", "int8"
    except ImportError:
        pass
    return "cpu", "int8"


def _speaker_label(raw: str) -> str:
    if raw.startswith("SPEAKER_"):
        num = raw.removeprefix("SPEAKER_").lstrip("0") or "0"
        return f"Speaker {int(num) + 1}"
    return raw


def _assign_speakers(
    whisper_segments: list[tuple[float, float, str]],
    diarization: list[tuple[float, float, str]],
) -> list[TranscriptSegment]:
    if not diarization:
        return [
            TranscriptSegment(start=s, end=e, speaker="Speaker 1", text=t)
            for s, e, t in whisper_segments
        ]

    assigned: list[TranscriptSegment] = []
    for start, end, text in whisper_segments:
        best_speaker = "Speaker 1"
        best_overlap = 0.0
        for d_start, d_end, label in diarization:
            overlap = max(0.0, min(end, d_end) - max(start, d_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = _speaker_label(label)
        assigned.append(
            TranscriptSegment(start=start, end=end, speaker=best_speaker, text=text),
        )
    return assigned


def _load_mono_waveform(audio_path: Path) -> dict[str, Any]:
    import torch
    from faster_whisper.audio import decode_audio

    samples = decode_audio(str(audio_path), sampling_rate=DIARIZATION_SAMPLE_RATE)
    waveform = torch.from_numpy(samples).unsqueeze(0)
    return {"waveform": waveform, "sample_rate": DIARIZATION_SAMPLE_RATE}


def _diarization_annotation(output: Any) -> Any:
    if hasattr(output, "exclusive_speaker_diarization"):
        return output.exclusive_speaker_diarization
    if hasattr(output, "speaker_diarization"):
        return output.speaker_diarization
    return output


def whisper_cache_path(audio_path: Path) -> Path:
    return audio_path.with_name(f"{audio_path.name}.whisper.json")


def save_whisper_cache(
    audio_path: Path,
    *,
    model_name: str,
    language: str | None,
    duration: float,
    segments: list[tuple[float, float, str]],
) -> Path:
    cache_path = whisper_cache_path(audio_path)
    payload = {
        "version": WHISPER_CACHE_VERSION,
        "model": model_name,
        "language": language,
        "duration": duration,
        "segments": [
            {"start": start, "end": end, "text": text}
            for start, end, text in segments
        ],
    }
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return cache_path


def load_whisper_cache(
    audio_path: Path,
    *,
    model_name: str,
    language: str | None,
) -> tuple[list[tuple[float, float, str]], float] | None:
    cache_path = whisper_cache_path(audio_path)
    if not cache_path.exists():
        return None

    payload = json.loads(cache_path.read_text())
    if payload.get("version") != WHISPER_CACHE_VERSION:
        return None
    if payload.get("model") != model_name:
        return None
    if payload.get("language") != language:
        return None

    segments = [
        (row["start"], row["end"], row["text"])
        for row in payload.get("segments", [])
    ]
    duration = float(payload.get("duration") or 0.0)
    return segments, duration


@dataclass
class _LocalModels:
    whisper: Any
    diarize_pipeline: Any | None
    device: str


class LocalTranscriber(Transcriber):
    """faster-whisper + pyannote diarization on this machine."""

    def __init__(
        self,
        *,
        model_name: str,
        device: str,
        compute_type: str,
        language: str | None,
        diarize: bool,
        hf_token: str | None,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._compute_type = compute_type
        self._language = language
        self._diarize = diarize
        self._hf_token = hf_token
        self._models: _LocalModels | None = None

    @classmethod
    def from_config(cls, config: Config) -> LocalTranscriber:
        return cls(
            model_name=config.transcription.model,
            device=config.transcription.device,
            compute_type=config.transcription.compute_type,
            language=config.transcription.language,
            diarize=config.transcription.diarize,
            hf_token=config.hf_token(),
        )

    @property
    def name(self) -> str:
        return "local"

    def supports_cache_reuse(self) -> bool:
        return True

    def prepare(self, audio_paths: list[Path], *, reuse_cache: bool = False) -> None:
        need_whisper = True
        if reuse_cache:
            need_whisper = any(
                load_whisper_cache(
                    path,
                    model_name=self._model_name,
                    language=self._language,
                )
                is None
                for path in audio_paths
            )
            if not need_whisper:
                _log("Reusing cached Whisper output for all pending file(s).")

        self._models = self._load_models(load_whisper=need_whisper)

    def close(self) -> None:
        self._models = None

    def transcribe(self, audio_path: Path, *, reuse_cache: bool = False) -> TranscriptionResult:
        if self._models is None:
            self.prepare([audio_path], reuse_cache=reuse_cache)

        assert self._models is not None
        segments, duration = self._transcribe_with_models(
            audio_path,
            self._models,
            reuse_whisper=reuse_cache,
        )
        return TranscriptionResult(segments=segments, duration_seconds=duration)

    def _load_models(self, *, load_whisper: bool) -> _LocalModels:
        whisper = None
        resolved_device, default_compute = _resolve_device(self._device)

        if load_whisper:
            from faster_whisper import WhisperModel

            compute = self._compute_type if self._compute_type != "default" else default_compute
            _log(
                f"Loading Whisper model ({self._model_name}, {resolved_device}) "
                "— first run may download weights...",
            )
            whisper = WhisperModel(self._model_name, device=resolved_device, compute_type=compute)
            _log("Whisper model ready.")

        diarize_pipeline = None
        if self._diarize:
            if not self._hf_token:
                raise RuntimeError(
                    "Diarization requires secrets.hf_token in config.yaml. "
                    "Get a token at https://huggingface.co/settings/tokens and accept "
                    f"https://huggingface.co/{DIARIZATION_MODEL}.",
                )
            from pyannote.audio import Pipeline

            _log("Loading pyannote diarization model — first run may download weights...")
            diarize_pipeline = Pipeline.from_pretrained(
                DIARIZATION_MODEL,
                token=self._hf_token,
            )
            if resolved_device == "cuda":
                import torch

                diarize_pipeline.to(torch.device("cuda"))
            _log("Diarization model ready.")

        return _LocalModels(
            whisper=whisper,
            diarize_pipeline=diarize_pipeline,
            device=resolved_device,
        )

    def _transcribe_with_models(
        self,
        audio_path: Path,
        models: _LocalModels,
        *,
        reuse_whisper: bool,
    ) -> tuple[list[TranscriptSegment], float | None]:
        whisper_segments: list[tuple[float, float, str]] = []
        duration = 0.0

        cached = (
            load_whisper_cache(
                audio_path,
                model_name=self._model_name,
                language=self._language,
            )
            if reuse_whisper
            else None
        )
        if cached is not None:
            whisper_segments, duration = cached
            _log(
                f"  Whisper: reusing cache ({len(whisper_segments)} segment(s), "
                f"{duration:.0f}s) — {whisper_cache_path(audio_path).name}",
            )
        else:
            if models.whisper is None:
                raise RuntimeError(
                    "Whisper model not loaded and no cached transcription is available.",
                )
            _log(f"  Whisper: transcribing {audio_path.name}...")
            segments_gen, info = models.whisper.transcribe(
                str(audio_path),
                language=self._language,
                beam_size=5,
                vad_filter=True,
            )

            duration = getattr(info, "duration", None) or 0.0
            last_pct = -1
            for seg in segments_gen:
                text = (seg.text or "").strip()
                if text:
                    whisper_segments.append((seg.start, seg.end, text))
                if duration > 0:
                    pct = min(100, int(seg.end / duration * 100))
                    if pct >= last_pct + 10 or pct == 100:
                        last_pct = pct
                        _log(f"  Whisper: {pct}% ({seg.end:.0f}s / {duration:.0f}s)")

            _log(f"  Whisper: done — {len(whisper_segments)} segment(s)")
            cache_path = save_whisper_cache(
                audio_path,
                model_name=self._model_name,
                language=self._language,
                duration=duration,
                segments=whisper_segments,
            )
            _log(f"  Whisper: cached to {cache_path.name}")

        diarization_rows: list[tuple[float, float, str]] = []
        if self._diarize and models.diarize_pipeline is not None:
            _log("  Diarization: running (can take several minutes on long recordings)...")
            diar_input = _load_mono_waveform(audio_path)
            diar_output = models.diarize_pipeline(diar_input)
            diar = _diarization_annotation(diar_output)
            for turn, _, speaker in diar.itertracks(yield_label=True):
                diarization_rows.append((turn.start, turn.end, speaker))
            speakers = len({s for _, _, s in diarization_rows})
            _log(f"  Diarization: done — {speakers} speaker(s) detected")

        segments = _assign_speakers(whisper_segments, diarization_rows)
        return segments, duration if duration > 0 else None
