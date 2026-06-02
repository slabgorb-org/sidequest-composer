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
