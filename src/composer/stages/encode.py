from pathlib import Path

from composer import tools
from composer.config import Config

# ffmpeg encoder arguments per output format.
_CODEC_ARGS = {
    "ogg": ["-c:a", "libvorbis", "-q:a", "5"],
    "mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
    "wav": ["-c:a", "pcm_s16le"],
}

SUPPORTED_FORMATS = tuple(_CODEC_ARGS)


def encode(in_wav: Path, out_path: Path, config: Config) -> Path:
    args = _CODEC_ARGS.get(config.output_format)
    if args is None:
        raise ValueError(
            f"unsupported output_format {config.output_format!r} "
            f"(choose from: {', '.join(_CODEC_ARGS)})"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tools.run([config.ffmpeg, "-y", "-i", str(in_wav), *args, str(out_path)])
    return out_path
