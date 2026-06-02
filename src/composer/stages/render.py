from pathlib import Path
from typing import Protocol

from composer import tools
from composer.config import Config
from composer.errors import RenderError
from composer.provenance import Provenance


class RenderBackend(Protocol):
    name: str

    def is_available(self) -> bool: ...
    def supports(self, source_format: str) -> bool: ...
    def render(self, score: Path, out_wav: Path, prov: Provenance) -> None: ...


class MuseScoreBackend:
    name = "musescore"
    formats = frozenset({"musicxml", "midi"})

    def __init__(self, config: Config):
        self.config = config

    def _binary(self) -> str | None:
        return tools.discover(self.config.musescore_candidates)

    def is_available(self) -> bool:
        return self._binary() is not None

    def supports(self, source_format: str) -> bool:
        return source_format in self.formats

    def render(self, score: Path, out_wav: Path, prov: Provenance) -> None:
        binary = self._binary()
        if binary is None:
            raise RenderError("MuseScore (mscore) not found")
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        tools.run([binary, "-o", str(out_wav), str(score)])
        prov.render_backend = self.name


class FluidSynthBackend:
    name = "fluidsynth"
    formats = frozenset({"midi"})

    def __init__(self, config: Config):
        self.config = config

    def _binary(self) -> str | None:
        return tools.discover(self.config.fluidsynth_candidates)

    def is_available(self) -> bool:
        return self._binary() is not None and self.config.soundfont is not None

    def supports(self, source_format: str) -> bool:
        return source_format in self.formats

    def render(self, score: Path, out_wav: Path, prov: Provenance) -> None:
        binary = self._binary()
        if binary is None:
            raise RenderError("FluidSynth not found")
        if self.config.soundfont is None:
            raise RenderError("FluidSynth backend requires a soundfont (--soundfont)")
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        tools.run([binary, "-ni", "-F", str(out_wav), str(self.config.soundfont), str(score)])
        prov.render_backend = self.name
        prov.soundfont = str(self.config.soundfont)


_BACKENDS = {"musescore": MuseScoreBackend, "fluidsynth": FluidSynthBackend}


def select_backend(config: Config, source_format: str, forced: str | None) -> RenderBackend:
    if forced is not None:
        if forced not in _BACKENDS:
            raise RenderError(
                f"unknown backend {forced!r} (choose from: {', '.join(_BACKENDS)})"
            )
        backend = _BACKENDS[forced](config)
        if not backend.is_available():
            raise RenderError(f"forced backend {forced!r} is not available")
        if not backend.supports(source_format):
            raise RenderError(f"backend {forced!r} cannot render {source_format} input")
        return backend

    for name in config.backend_order:
        backend = _BACKENDS[name](config)
        if backend.is_available() and backend.supports(source_format):
            return backend

    raise RenderError(
        f"no available render backend supports {source_format} input "
        f"(checked: {', '.join(config.backend_order)})"
    )
