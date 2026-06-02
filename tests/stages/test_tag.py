import shutil
import struct
import subprocess

import pytest
from mutagen.ogg import OggPage
from mutagen.oggvorbis import OggVorbis

from composer.provenance import Provenance
from composer.stages.tag import tag

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg needed for audio fixture setup"
)


def _make_ogg_vorbis(path):
    """Write a minimal valid OGG Vorbis file that mutagen can open and tag."""
    serial = 0x12345678
    vendor = b"test"

    ident_pkt = (
        b"\x01vorbis"
        + struct.pack("<I", 0)       # version
        + struct.pack("<B", 1)       # channels (mono)
        + struct.pack("<I", 44100)   # sample_rate
        + struct.pack("<i", 0)       # bitrate_max
        + struct.pack("<i", 112000)  # bitrate_nom
        + struct.pack("<i", 0)       # bitrate_min
        + struct.pack("<B", 0xB8)    # blocksize nibbles (256 | 2048<<4)
        + struct.pack("<B", 1)       # framing bit
    )
    comment_pkt = (
        b"\x03vorbis"
        + struct.pack("<I", len(vendor))
        + vendor
        + struct.pack("<I", 0)  # 0 user comments
        + struct.pack("<B", 1)  # framing bit
    )
    setup_pkt = b"\x05vorbis\x01"  # minimal setup header + framing bit

    p0 = OggPage()
    p0.serial = serial
    p0.sequence = 0
    p0.packets = [ident_pkt]
    p0._OggPage__type_flags = 2  # BOS

    p1 = OggPage()
    p1.serial = serial
    p1.sequence = 1
    p1.packets = [comment_pkt]

    p2 = OggPage()
    p2.serial = serial
    p2.sequence = 2
    p2.packets = [setup_pkt]
    p2._OggPage__type_flags = 4  # EOS

    with open(path, "wb") as f:
        f.write(p0.write() + p1.write() + p2.write())


@requires_ffmpeg
def test_provenance_round_trips_through_ogg(tmp_path):
    # Confirm ffmpeg is functional (the skip marker already gates on its presence).
    subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)

    ogg = tmp_path / "track.ogg"
    _make_ogg_vorbis(ogg)

    prov = Provenance(
        title="Gymnopedie No. 1",
        composer="Erik Satie",
        render_backend="musescore",
        loudness_target=-16.0,
    )
    tag(ogg, prov)

    read = OggVorbis(ogg)
    assert read["SOURCE"] == ["public-domain score"]
    assert read["RENDERED_LOCALLY"] == ["true"]
    assert read["TITLE"] == ["Gymnopedie No. 1"]
    assert read["RENDER_BACKEND"] == ["musescore"]
    assert read["LOUDNESS_TARGET_LUFS"] == ["-16.0"]
