from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class PieceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    source_url: str
    composer: str | None = None
    work: str | None = None
    movement: str | None = None
    # per-entry overrides
    backend: str | None = None
    loudness: float | None = None
    soundfont: str | None = None
    out_name: str | None = None

    def resolved(self, manifest: "Manifest") -> "PieceEntry":
        """Return a copy with top-level defaults filled in where entry is unset."""
        return self.model_copy(
            update={
                "backend": self.backend or manifest.backend,
                "loudness": self.loudness if self.loudness is not None else manifest.loudness,
                "soundfont": self.soundfont or manifest.soundfont,
            }
        )


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend: str | None = None
    loudness: float | None = None
    soundfont: str | None = None
    out_dir: str | None = None
    entries: list[PieceEntry] = []


def load_manifest(path: str | Path) -> Manifest:
    data = yaml.safe_load(Path(path).read_text()) or {}
    return Manifest.model_validate(data)


def from_input(value: str) -> Manifest:
    """Accept a manifest path, a score file path, or a URL; always return a Manifest."""
    lowered = value.lower()
    if lowered.endswith((".yaml", ".yml")):
        return load_manifest(value)
    title = Path(value.split("?")[0]).stem
    return Manifest(entries=[PieceEntry(title=title, source_url=value)])
