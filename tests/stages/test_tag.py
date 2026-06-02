import subprocess

import pytest
from mutagen.mp3 import MP3
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE

from composer import tools
from composer.provenance import Provenance
from composer.stages.tag import tag


def _maybe_ffmpeg():
    try:
        return tools.resolve_ffmpeg_tools()[0]
    except Exception:
        return None


requires_ffmpeg = pytest.mark.skipif(
    _maybe_ffmpeg() is None, reason="static-ffmpeg unavailable to mint an audio fixture"
)


def _mint(ffmpeg, path, codec):
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
         "-t", "0.1", "-c:a", codec, str(path)],
        check=True, capture_output=True,
    )


def _prov():
    return Provenance(
        title="Gymnopedie No. 1", composer="Erik Satie",
        render_backend="musescore", loudness_target=-16.0,
    )


@requires_ffmpeg
def test_provenance_round_trips_through_ogg(tmp_path):
    ffmpeg = tools.resolve_ffmpeg_tools()[0]
    ogg = tmp_path / "track.ogg"
    _mint(ffmpeg, ogg, "libvorbis")

    tag(ogg, _prov(), "ogg")

    read = OggVorbis(ogg)
    assert read["SOURCE"] == ["public-domain score"]
    assert read["RENDERED_LOCALLY"] == ["true"]
    assert read["TITLE"] == ["Gymnopedie No. 1"]
    assert read["RENDER_BACKEND"] == ["musescore"]
    assert read["LOUDNESS_TARGET_LUFS"] == ["-16.0"]


@requires_ffmpeg
def test_provenance_round_trips_through_mp3(tmp_path):
    ffmpeg = tools.resolve_ffmpeg_tools()[0]
    mp3 = tmp_path / "track.mp3"
    _mint(ffmpeg, mp3, "libmp3lame")

    tag(mp3, _prov(), "mp3")

    read = MP3(mp3)
    assert read.tags["TXXX:SOURCE"].text == ["public-domain score"]
    assert read.tags["TXXX:RENDERED_LOCALLY"].text == ["true"]
    assert read.tags["TXXX:RENDER_BACKEND"].text == ["musescore"]
    assert read.tags["TIT2"].text == ["Gymnopedie No. 1"]


@requires_ffmpeg
def test_provenance_round_trips_through_wav(tmp_path):
    ffmpeg = tools.resolve_ffmpeg_tools()[0]
    wav = tmp_path / "track.wav"
    _mint(ffmpeg, wav, "pcm_s16le")

    tag(wav, _prov(), "wav")

    read = WAVE(wav)
    assert read.tags["TXXX:SOURCE"].text == ["public-domain score"]
    assert read.tags["TXXX:RENDERED_LOCALLY"].text == ["true"]
    assert read.tags["TXXX:RENDER_BACKEND"].text == ["musescore"]
