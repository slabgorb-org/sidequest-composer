import os
import subprocess

import pytest

from composer import tools


def _maybe_resolve():
    try:
        return tools.resolve_ffmpeg_tools()
    except Exception:
        return None


@pytest.mark.skipif(_maybe_resolve() is None, reason="static-ffmpeg binary unavailable (offline?)")
def test_resolved_ffmpeg_exists_and_supports_libvorbis():
    ffmpeg, ffprobe = tools.resolve_ffmpeg_tools()
    assert os.path.exists(ffmpeg)
    assert os.path.exists(ffprobe)
    encoders = subprocess.run(
        [ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True, check=True
    )
    assert "libvorbis" in encoders.stdout
