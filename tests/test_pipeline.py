from pathlib import Path

import composer
from composer import pipeline
from composer.config import Config
from composer.manifest import Manifest, PieceEntry


def _stub_stages(monkeypatch, fail_titles=()):
    """Replace every external stage with an in-process stub."""
    def fake_fetch(self, url, prov):
        prov.score_format = "midi"
        prov.source_sha256 = "deadbeef"
        return Path(url)

    monkeypatch.setattr(pipeline.UrlFetcher, "fetch", fake_fetch)

    class FakeBackend:
        name = "musescore"
        audio_suffix = ".wav"

        def render(self, score, out_audio, prov):
            prov.render_backend = "musescore"
            out_audio.parent.mkdir(parents=True, exist_ok=True)
            out_audio.write_bytes(b"WAV")

    def fake_select(config, source_format, forced):
        return FakeBackend()

    def fake_normalize(in_wav, out_wav, target_lufs, config, prov):
        prov.loudness_target = target_lufs
        out_wav.write_bytes(b"WAV")
        return out_wav

    def fake_encode(in_wav, out_ogg, config):
        out_ogg.write_bytes(b"OGG")
        return out_ogg

    def fake_tag(path, prov, output_format):
        if prov.title in fail_titles:
            raise RuntimeError("boom")

    monkeypatch.setattr(pipeline, "select_backend", fake_select)
    monkeypatch.setattr(pipeline, "normalize", fake_normalize)
    monkeypatch.setattr(pipeline, "encode", fake_encode)
    monkeypatch.setattr(pipeline, "tag", fake_tag)


def test_run_piece_produces_tagged_output(monkeypatch, tmp_path):
    _stub_stages(monkeypatch)
    cfg = Config(out_dir=tmp_path / "out", cache_dir=tmp_path / "cache")
    entry = PieceEntry(title="A", source_url="a.midi", loudness=-16.0)

    result = pipeline.run_piece(entry, cfg)

    assert result.ok
    assert result.output_path.exists()
    assert result.output_path.suffix == ".ogg"
    assert result.provenance.tool_version == composer.__version__
    assert result.provenance.render_date is not None
    assert result.provenance.fetch_date is not None


def test_output_format_drives_extension(monkeypatch, tmp_path):
    _stub_stages(monkeypatch)
    cfg = Config(out_dir=tmp_path / "out", cache_dir=tmp_path / "cache", output_format="mp3")
    entry = PieceEntry(title="A", source_url="a.midi", loudness=-16.0)

    result = pipeline.run_piece(entry, cfg)

    assert result.ok
    assert result.output_path.suffix == ".mp3"


def test_run_isolates_failing_piece(monkeypatch, tmp_path):
    _stub_stages(monkeypatch, fail_titles={"bad"})
    cfg = Config(out_dir=tmp_path / "out", cache_dir=tmp_path / "cache")
    manifest = Manifest(
        loudness=-16.0,
        entries=[
            PieceEntry(title="good", source_url="g.midi"),
            PieceEntry(title="bad", source_url="b.midi"),
        ],
    )

    report = pipeline.run(manifest, cfg)

    assert report.succeeded == 1
    assert report.failed == 1
    assert any(not r.ok and "boom" in (r.error or "") for r in report.results)
    assert report.exit_code == 1
