from pathlib import Path

from mutagen.id3 import TIT2, TPE1, TXXX
from mutagen.mp3 import MP3
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE

from composer.provenance import Provenance


def tag(path: Path, prov: Provenance, output_format: str) -> None:
    """Write the provenance accumulator into the output file's metadata.

    OGG carries it as native Vorbis comments; MP3 and WAV carry it as ID3
    user-defined (TXXX) frames. Either way the legal-core fields ride along.
    """
    comments = prov.to_vorbis_comments()
    if output_format == "ogg":
        audio = OggVorbis(path)
        for key, value in comments.items():
            audio[key] = value
        audio.save()
    elif output_format in ("mp3", "wav"):
        _tag_id3(path, output_format, comments)
    else:
        raise ValueError(f"cannot tag unsupported output_format {output_format!r}")


def _tag_id3(path: Path, output_format: str, comments: dict[str, str]) -> None:
    audio = MP3(path) if output_format == "mp3" else WAVE(path)
    if audio.tags is None:
        audio.add_tags()
    tags = audio.tags
    for key, value in comments.items():
        tags.add(TXXX(encoding=3, desc=key, text=value))
    # Mirror title/artist into the standard frames so players display them.
    if comments.get("TITLE"):
        tags.add(TIT2(encoding=3, text=comments["TITLE"]))
    if comments.get("ARTIST"):
        tags.add(TPE1(encoding=3, text=comments["ARTIST"]))
    audio.save()
