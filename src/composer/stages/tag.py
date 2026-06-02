from pathlib import Path

from mutagen.oggvorbis import OggVorbis

from composer.provenance import Provenance


def tag(ogg_path: Path, prov: Provenance) -> None:
    audio = OggVorbis(ogg_path)
    for key, value in prov.to_vorbis_comments().items():
        audio[key] = value
    audio.save()
