from pathlib import Path

from composer.config import Config
from composer.stages import encode


def test_encode_builds_ogg_command(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(encode.tools, "run", lambda cmd, check=True: calls.append(cmd))

    out = tmp_path / "track.ogg"
    result = encode.encode(Path("norm.wav"), out, Config())

    assert result == out
    cmd = " ".join(calls[0])
    assert "libvorbis" in cmd
    assert str(out) in cmd
    assert "norm.wav" in cmd


def test_encode_mp3_uses_libmp3lame(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(encode.tools, "run", lambda cmd, check=True: calls.append(cmd))

    out = tmp_path / "track.mp3"
    encode.encode(Path("norm.wav"), out, Config(output_format="mp3"))

    assert "libmp3lame" in " ".join(calls[0])


def test_encode_wav_uses_pcm(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(encode.tools, "run", lambda cmd, check=True: calls.append(cmd))

    out = tmp_path / "track.wav"
    encode.encode(Path("norm.wav"), out, Config(output_format="wav"))

    assert "pcm_s16le" in " ".join(calls[0])


def test_encode_rejects_unknown_format(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        encode.encode(Path("norm.wav"), tmp_path / "x.flac", Config(output_format="flac"))
