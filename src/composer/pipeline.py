from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import composer
from composer.config import Config
from composer.manifest import Manifest, PieceEntry
from composer.provenance import Provenance
from composer.stages.encode import encode
from composer.stages.fetch import UrlFetcher
from composer.stages.normalize import normalize
from composer.stages.render import select_backend
from composer.stages.tag import tag


@dataclass
class PieceResult:
    title: str
    ok: bool
    output_path: Path | None = None
    provenance: Provenance | None = None
    error: str | None = None


@dataclass
class Report:
    results: list[PieceResult] = field(default_factory=list)

    @property
    def succeeded(self) -> int:
        return sum(1 for r in self.results if r.ok)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.ok)

    @property
    def exit_code(self) -> int:
        return 1 if self.failed else 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_piece(entry: PieceEntry, config: Config) -> PieceResult:
    prov = Provenance(
        title=entry.title, composer=entry.composer, work=entry.work, movement=entry.movement
    )
    work_dir = config.out_dir / "_work"
    out_name = entry.out_name or entry.title
    norm_wav = work_dir / f"{out_name}.norm.wav"
    out_path = config.out_dir / f"{out_name}.{config.output_format}"

    score = UrlFetcher(config.cache_dir).fetch(entry.source_url, prov)
    prov.fetch_date = _now()
    backend = select_backend(config, source_format=prov.score_format, forced=entry.backend)
    raw_audio = work_dir / f"{out_name}.raw{backend.audio_suffix}"
    backend.render(score, raw_audio, prov)
    target = entry.loudness if entry.loudness is not None else config.loudness
    normalize(raw_audio, norm_wav, target_lufs=target, config=config, prov=prov)
    encode(norm_wav, out_path, config)

    prov.tool_version = composer.__version__
    prov.render_date = _now()
    tag(out_path, prov, config.output_format)

    return PieceResult(title=entry.title, ok=True, output_path=out_path, provenance=prov)


def run(manifest: Manifest, config: Config) -> Report:
    report = Report()
    for entry in manifest.entries:
        resolved = entry.resolved(manifest)
        try:
            report.results.append(run_piece(resolved, config))
        except Exception as exc:  # per-piece isolation
            report.results.append(PieceResult(title=entry.title, ok=False, error=str(exc)))
    return report
