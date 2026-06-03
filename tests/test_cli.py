from typer.testing import CliRunner

from composer import cli
from composer.pipeline import PieceResult, Report

runner = CliRunner()


def test_render_reports_success(monkeypatch, tmp_path):
    captured = {}

    def fake_run(manifest, config):
        captured["manifest"] = manifest
        captured["config"] = config
        return Report(results=[PieceResult(title="A", ok=True, output_path=tmp_path / "A.ogg")])

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli, "resolve_ffmpeg_tools", lambda: ("ffmpeg-stub", "ffprobe-stub"))

    score = tmp_path / "song.midi"
    score.write_bytes(b"MThd")
    result = runner.invoke(cli.app, ["render", str(score), "--out-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "1 succeeded" in result.stdout
    assert captured["manifest"].entries[0].source_url == str(score)
    assert captured["config"].out_dir == tmp_path
    assert captured["config"].ffmpeg == "ffmpeg-stub"
    assert captured["config"].ffprobe == "ffprobe-stub"
    assert captured["config"].output_format == "ogg"  # default


def test_format_option_sets_output_format(monkeypatch, tmp_path):
    captured = {}

    def fake_run(manifest, config):
        captured["config"] = config
        return Report(results=[PieceResult(title="A", ok=True, output_path=tmp_path / "A.mp3")])

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli, "resolve_ffmpeg_tools", lambda: ("ffmpeg-stub", "ffprobe-stub"))

    score = tmp_path / "song.midi"
    score.write_bytes(b"MThd")
    result = runner.invoke(cli.app, ["render", str(score), "--format", "mp3"])

    assert result.exit_code == 0
    assert captured["config"].output_format == "mp3"


def test_unknown_format_exits_nonzero(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "resolve_ffmpeg_tools", lambda: ("ffmpeg-stub", "ffprobe-stub"))
    score = tmp_path / "song.midi"
    score.write_bytes(b"MThd")

    result = runner.invoke(cli.app, ["render", str(score), "--format", "flac"])

    assert result.exit_code == 2
    assert "flac" in result.stdout


def test_render_nonzero_exit_on_failure(monkeypatch, tmp_path):
    def fake_run(manifest, config):
        return Report(results=[PieceResult(title="A", ok=False, error="boom")])

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli, "resolve_ffmpeg_tools", lambda: ("ffmpeg-stub", "ffprobe-stub"))
    score = tmp_path / "song.midi"
    score.write_bytes(b"MThd")

    result = runner.invoke(cli.app, ["render", str(score)])

    assert result.exit_code == 1
    assert "boom" in result.stdout
