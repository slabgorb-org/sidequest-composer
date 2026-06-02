import json
import subprocess
from pathlib import Path

from composer.config import Config
from composer.provenance import Provenance
from composer.stages import normalize


_MEASURE_JSON = {
    "input_i": "-23.4",
    "input_tp": "-5.2",
    "input_lra": "7.1",
    "input_thresh": "-34.1",
    "target_offset": "0.5",
}


def _fake_completed(stdout="", stderr="", code=0):
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout, stderr=stderr)


def test_two_pass_measures_then_applies(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, check=True):
        calls.append(cmd)
        if "print_format=json" in " ".join(cmd):
            # ffmpeg writes loudnorm json to stderr
            return _fake_completed(stderr="ffmpeg...\n" + json.dumps(_MEASURE_JSON))
        return _fake_completed()

    monkeypatch.setattr(normalize.tools, "run", fake_run)

    prov = Provenance(title="x")
    out = tmp_path / "norm.wav"
    normalize.normalize(Path("raw.wav"), out, target_lufs=-16.0, config=Config(), prov=prov)

    assert len(calls) == 2
    measure_cmd, apply_cmd = " ".join(calls[0]), " ".join(calls[1])
    assert "print_format=json" in measure_cmd
    assert "measured_I=-23.4" in apply_cmd
    assert "measured_TP=-5.2" in apply_cmd
    assert "offset=0.5" in apply_cmd
    assert "I=-16.0" in apply_cmd
    assert prov.loudness_target == -16.0
    assert prov.measured_loudness == -23.4
