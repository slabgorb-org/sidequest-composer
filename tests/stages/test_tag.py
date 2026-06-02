import subprocess

import pytest
from mutagen.oggvorbis import OggVorbis

from composer import tools
from composer.provenance import Provenance
from composer.stages.tag import tag


def _maybe_ffmpeg():
    try:
        return tools.resolve_ffmpeg_tools()[0]
    except Exception:
        return None


requires_ffmpeg = pytest.mark.skipif(
    _maybe_ffmpeg() is None, reason="static-ffmpeg (libvorbis) unavailable to mint an OGG fixture"
)


@requires_ffmpeg
def test_provenance_round_trips_through_ogg(tmp_path):
    ffmpeg = tools.resolve_ffmpeg_tools()[0]
    ogg = tmp_path / "track.ogg"
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
         "-t", "0.1", "-c:a", "libvorbis", str(ogg)],
        check=True, capture_output=True,
    )

    prov = Provenance(
        title="Gymnopedie No. 1", composer="Erik Satie",
        render_backend="musescore", loudness_target=-16.0,
    )
    tag(ogg, prov)

    read = OggVorbis(ogg)
    assert read["SOURCE"] == ["public-domain score"]
    assert read["RENDERED_LOCALLY"] == ["true"]
    assert read["TITLE"] == ["Gymnopedie No. 1"]
    assert read["RENDER_BACKEND"] == ["musescore"]
    assert read["LOUDNESS_TARGET_LUFS"] == ["-16.0"]
