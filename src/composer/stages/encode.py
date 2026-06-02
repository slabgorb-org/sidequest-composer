from pathlib import Path

from composer import tools
from composer.config import Config


def encode(in_wav: Path, out_ogg: Path, config: Config) -> Path:
    out_ogg.parent.mkdir(parents=True, exist_ok=True)
    tools.run(
        [config.ffmpeg, "-y", "-i", str(in_wav), "-c:a", "libvorbis", "-q:a", "5", str(out_ogg)]
    )
    return out_ogg
