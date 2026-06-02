from pathlib import Path

import pytest

from composer import tools
from composer.config import Config
from composer.errors import RenderError
from composer.provenance import Provenance
from composer.stages import render
from composer.stages.render import MuseScoreBackend, FluidSynthBackend, select_backend


def test_backends_declare_producible_audio_suffix():
    # MuseScore 4 cannot write WAV/FLAC reliably, so it renders compressed audio;
    # FluidSynth writes WAV. The pipeline names the raw render file accordingly.
    assert MuseScoreBackend(Config()).audio_suffix == ".mp3"
    assert FluidSynthBackend(Config()).audio_suffix == ".wav"


def test_musescore_builds_correct_command(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(tools, "discover", lambda c: "/bin/mscore")
    monkeypatch.setattr(render.tools, "run", lambda cmd, check=True: calls.append(cmd))

    backend = MuseScoreBackend(Config())
    out = tmp_path / "out.wav"
    backend.render(Path("score.musicxml"), out, Provenance(title="x"))

    assert calls[0] == ["/bin/mscore", "-o", str(out), "score.musicxml"]


def test_musescore_stamps_provenance(monkeypatch, tmp_path):
    monkeypatch.setattr(tools, "discover", lambda c: "/bin/mscore")
    monkeypatch.setattr(render.tools, "run", lambda cmd, check=True: None)
    prov = Provenance(title="x")

    MuseScoreBackend(Config()).render(Path("s.musicxml"), tmp_path / "o.wav", prov)

    assert prov.render_backend == "musescore"


def test_fluidsynth_rejects_musicxml(monkeypatch, tmp_path):
    monkeypatch.setattr(tools, "discover", lambda c: "/bin/fluidsynth")
    backend = FluidSynthBackend(Config(soundfont=Path("x.sf2")))
    assert backend.supports("musicxml") is False
    assert backend.supports("midi") is True


def test_select_prefers_first_available_supporting_format(monkeypatch):
    monkeypatch.setattr(
        tools, "discover",
        lambda c: "/bin/mscore" if "mscore" in c[0] or "MuseScore" in str(c) else None,
    )
    backend = select_backend(Config(), source_format="musicxml", forced=None)
    assert backend.name == "musescore"


def test_select_falls_back_when_default_missing(monkeypatch):
    # MuseScore absent, FluidSynth present, MIDI source -> fall back to fluidsynth
    monkeypatch.setattr(
        tools, "discover",
        lambda c: "/bin/fluidsynth" if c and "fluidsynth" in c[0] else None,
    )
    backend = select_backend(Config(soundfont=Path("x.sf2")), source_format="midi", forced=None)
    assert backend.name == "fluidsynth"


def test_select_raises_when_no_capable_backend(monkeypatch):
    # Only FluidSynth available but source is MusicXML -> no honest fallback
    monkeypatch.setattr(
        tools, "discover",
        lambda c: "/bin/fluidsynth" if c and "fluidsynth" in c[0] else None,
    )
    with pytest.raises(RenderError):
        select_backend(Config(soundfont=Path("x.sf2")), source_format="musicxml", forced=None)


def test_forced_backend_no_fallback(monkeypatch):
    monkeypatch.setattr(tools, "discover", lambda c: None)
    with pytest.raises(RenderError):
        select_backend(Config(), source_format="midi", forced="musescore")


def test_forced_unknown_backend_raises_render_error():
    with pytest.raises(RenderError):
        select_backend(Config(), source_format="midi", forced="bogus")
