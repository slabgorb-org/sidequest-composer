from dataclasses import dataclass, field
from pathlib import Path

_MUSESCORE_CANDIDATES = (
    "mscore",
    "mscore4",
    "musescore",
    "/Applications/MuseScore 4.app/Contents/MacOS/mscore",
)
_FLUIDSYNTH_CANDIDATES = ("fluidsynth",)


@dataclass
class Config:
    backend_order: tuple[str, ...] = ("musescore", "fluidsynth")
    loudness: float = -16.0
    out_dir: Path = field(default_factory=lambda: Path("out"))
    cache_dir: Path = field(default_factory=lambda: Path(".cache/scores"))
    soundfont: Path | None = None
    output_format: str = "ogg"

    musescore_candidates: tuple[str, ...] = _MUSESCORE_CANDIDATES
    fluidsynth_candidates: tuple[str, ...] = _FLUIDSYNTH_CANDIDATES
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
