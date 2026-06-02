import json
from pathlib import Path

from composer import tools
from composer.config import Config
from composer.errors import NormalizeError
from composer.provenance import Provenance

_TP = -1.5
_LRA = 11.0


def _parse_measure(stderr: str) -> dict:
    start = stderr.rfind("{")
    end = stderr.rfind("}")
    if start == -1 or end == -1:
        raise NormalizeError("could not parse loudnorm measurement from ffmpeg output")
    return json.loads(stderr[start : end + 1])


def normalize(
    in_wav: Path, out_wav: Path, target_lufs: float, config: Config, prov: Provenance
) -> Path:
    base_filter = f"loudnorm=I={target_lufs}:TP={_TP}:LRA={_LRA}"

    measure = tools.run(
        [
            config.ffmpeg,
            "-i",
            str(in_wav),
            "-af",
            f"{base_filter}:print_format=json",
            "-f",
            "null",
            "-",
        ]
    )
    m = _parse_measure(measure.stderr)

    apply_filter = (
        f"{base_filter}"
        f":measured_I={m['input_i']}"
        f":measured_TP={m['input_tp']}"
        f":measured_LRA={m['input_lra']}"
        f":measured_thresh={m['input_thresh']}"
        f":offset={m['target_offset']}"
        f":linear=true"
    )
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    tools.run(
        [config.ffmpeg, "-y", "-i", str(in_wav), "-af", apply_filter, "-ar", "48000", str(out_wav)]
    )

    prov.loudness_target = target_lufs
    prov.measured_loudness = float(m["input_i"])
    return out_wav
