import shutil
from pathlib import Path

import pytest
from mutagen.oggvorbis import OggVorbis

from composer import tools
from composer.config import Config
from composer.manifest import load_manifest
from composer.pipeline import run

MANIFEST = Path(__file__).parent / "data" / "gymnopedie.manifest.yaml"


def _musescore_present() -> bool:
    candidates = Config().musescore_candidates
    return any(shutil.which(c) for c in candidates) or any(Path(c).exists() for c in candidates)


def _ffmpeg_available() -> bool:
    try:
        tools.resolve_ffmpeg_tools()
        return True
    except Exception:
        return False


requires_toolchain = pytest.mark.skipif(
    not _ffmpeg_available() or not _musescore_present(),
    reason="needs MuseScore 4 + a libvorbis-capable ffmpeg installed",
)


@requires_toolchain
def test_gymnopedie_renders_to_tagged_ogg(tmp_path):
    ffmpeg, ffprobe = tools.resolve_ffmpeg_tools()
    manifest = load_manifest(MANIFEST)
    config = Config(
        out_dir=tmp_path / "out",
        cache_dir=tmp_path / "cache",
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
    )

    report = run(manifest, config)

    assert report.failed == 0, [r.error for r in report.results if not r.ok]
    out = report.results[0].output_path
    assert out.exists() and out.suffix == ".ogg"

    tags = OggVorbis(out)
    assert tags["SOURCE"] == ["public-domain score"]
    assert tags["RENDERED_LOCALLY"] == ["true"]
    assert tags["RENDER_BACKEND"] == ["musescore"]
