from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Type

from hidock.transcribers.base import Transcriber

if TYPE_CHECKING:
    from hidock.config import Config

_BUILTIN_PATHS: dict[str, str] = {
    "local": "hidock.transcribers.local.LocalTranscriber",
    "assemblyai": "hidock.transcribers.assemblyai.AssemblyAITranscriber",
    "remote": "hidock.transcribers.remote.RemoteTranscriber",
}


def _import_class(dotted_path: str) -> Type[Transcriber]:
    module_path, _, class_name = dotted_path.rpartition(".")
    if not module_path or not class_name:
        raise ValueError(
            f"Invalid transcription.custom_class {dotted_path!r} — "
            "expected form 'package.module.ClassName'.",
        )
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    if not isinstance(cls, type) or not issubclass(cls, Transcriber):
        raise TypeError(f"{dotted_path} must be a Transcriber subclass.")
    return cls


def _load_builtin(provider: str) -> Type[Transcriber]:
    dotted_path = _BUILTIN_PATHS.get(provider)
    if dotted_path is None:
        known = ", ".join(sorted({*_BUILTIN_PATHS, "custom"}))
        raise ValueError(f"Unknown transcription.provider {provider!r}. Known: {known}.")
    return _import_class(dotted_path)


def get_transcriber(config: Config) -> Transcriber:
    provider = (config.transcription.provider or "assemblyai").strip().lower()

    if provider == "custom":
        custom_class = (config.transcription.custom_class or "").strip()
        if not custom_class:
            raise RuntimeError(
                "transcription.provider is custom but transcription.custom_class is not set.",
            )
        cls = _import_class(custom_class)
        return cls.from_config(config)

    cls = _load_builtin(provider)
    return cls.from_config(config)
