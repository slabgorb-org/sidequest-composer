from pathlib import Path

from composer.config import Config


def test_defaults():
    cfg = Config()
    assert cfg.loudness == -16.0
    assert cfg.backend_order == ("musescore", "fluidsynth")
    assert cfg.out_dir == Path("out")
    assert cfg.cache_dir == Path(".cache/scores")
    assert cfg.soundfont is None


def test_musescore_candidate_paths_include_macos_bundle():
    cfg = Config()
    assert any("MuseScore 4.app" in p for p in cfg.musescore_candidates)
    assert "mscore" in cfg.musescore_candidates
