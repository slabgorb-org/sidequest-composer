# Pipeline Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, offline CLI that renders public-domain notation (MusicXML/MIDI) into tagged, loudness-normalized OGG audio, manifest-driven, with provenance baked into the artifact.

**Architecture:** Explicit named pipeline stages (fetch → render → normalize → encode → tag) wired by a thin orchestrator. All external tools (MuseScore, FluidSynth, ffmpeg) are invoked as subprocesses through a single `tools.run` boundary, which tests mock. `Protocol` seams exist only at the render backend and the fetcher. A per-piece `Provenance` accumulator flows alongside the data and is written as Vorbis comments at the end.

**Tech Stack:** Python 3.14, `uv` (packaging/venv), Typer (CLI), pydantic v2 (manifest models), mutagen (Vorbis comment tags), stdlib `subprocess`/`hashlib`/`urllib`/`json`, ffmpeg/ffprobe + MuseScore 4/FluidSynth as external subprocesses.

**Reference spec:** `docs/superpowers/specs/2026-06-02-pipeline-architecture-design.md`

---

## Design clarifications discovered during planning

1. **Backends are not universally interchangeable by input format.** MuseScore reads MusicXML *and* MIDI; FluidSynth reads MIDI only. Each backend therefore declares `supported_formats`. The selector falls back only to a backend that supports the source's format. A MusicXML source with only FluidSynth available is a clear hard error, not a silent failure. This preserves the spec's "MuseScore default, auto-fallback" while staying honest.
2. **MuseScore on macOS is an app bundle.** Tool discovery probes PATH names *and* the known bundle path `/Applications/MuseScore 4.app/Contents/MacOS/mscore`.
3. **Provenance is the one accumulator.** Data payloads (file paths) flow explicitly stage-to-stage; the `Provenance` object is passed alongside and stamped by each stage. This satisfies "explicit typed in/out, not one mutable blob" — the blob is only the provenance record, which is *meant* to accumulate.

## File structure

```
pyproject.toml                  # uv project, deps, pytest config, console script
src/composer/__init__.py        # version
src/composer/config.py          # Config dataclass + defaults + MuseScore bundle paths
src/composer/tools.py           # run() subprocess wrapper, discover(), version(), ToolError
src/composer/provenance.py      # Provenance dataclass + to_vorbis_comments()
src/composer/manifest.py        # PieceEntry, Manifest (pydantic), load + from_input + resolve
src/composer/errors.py          # RenderError, FetchError, NormalizeError
src/composer/stages/__init__.py
src/composer/stages/fetch.py    # Fetcher protocol, UrlFetcher (download + sha256 cache)
src/composer/stages/render.py   # RenderBackend protocol, MuseScore/FluidSynth backends, select_backend
src/composer/stages/normalize.py# loudnorm two-pass (measure + apply)
src/composer/stages/encode.py   # WAV -> OGG
src/composer/stages/tag.py      # write Provenance as Vorbis comments
src/composer/pipeline.py        # PieceResult, Report, run_piece, run
src/composer/cli.py             # Typer app: `composer render <input> [opts]`
tests/...                       # mirrors src tree
```

---

### Task 1: Project scaffold and tooling

**Files:**
- Create: `pyproject.toml`
- Create: `src/composer/__init__.py`
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Write the failing test**

`tests/test_smoke.py`:
```python
import composer


def test_version_is_exposed():
    assert composer.__version__ == "0.1.0"
```

- [ ] **Step 2: Create the project files**

`pyproject.toml`:
```toml
[project]
name = "sidequest-composer"
version = "0.1.0"
description = "Render public-domain notation into tagged, rights-free audio."
requires-python = ">=3.12"
dependencies = [
    "typer>=0.12",
    "pydantic>=2.6",
    "mutagen>=1.47",
]

[project.scripts]
composer = "composer.cli:app"

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.5"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/composer"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
```

`src/composer/__init__.py`:
```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Install and run the test**

Run: `uv sync && uv run pytest tests/test_smoke.py -v`
Expected: PASS (1 passed).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock src/composer/__init__.py tests/test_smoke.py
git commit -m "chore: scaffold composer package with uv + pytest"
```

---

### Task 2: Config defaults

**Files:**
- Create: `src/composer/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'composer.config'`.

- [ ] **Step 3: Write minimal implementation**

`src/composer/config.py`:
```python
from dataclasses import dataclass, field
from pathlib import Path

_MUSESCORE_CANDIDATES = (
    "mscore",
    "mscore4",
    "musescore",
    "/Applications/MuseScore 4.app/Contents/MacOS/mscore",
)
_FLUIDSYNTH_CANDIDATES = ("fluidsynth",)


@dataclass
class Config:
    backend_order: tuple[str, ...] = ("musescore", "fluidsynth")
    loudness: float = -16.0
    out_dir: Path = field(default_factory=lambda: Path("out"))
    cache_dir: Path = field(default_factory=lambda: Path(".cache/scores"))
    soundfont: Path | None = None
    output_format: str = "ogg"

    musescore_candidates: tuple[str, ...] = _MUSESCORE_CANDIDATES
    fluidsynth_candidates: tuple[str, ...] = _FLUIDSYNTH_CANDIDATES
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/composer/config.py tests/test_config.py
git commit -m "feat: add Config with defaults and MuseScore bundle discovery paths"
```

---

### Task 3: Tool subprocess boundary

This is the single seam every stage uses to call external tools, so tests can mock it in one place.

**Files:**
- Create: `src/composer/errors.py`
- Create: `src/composer/tools.py`
- Test: `tests/test_tools.py`

- [ ] **Step 1: Write the failing test**

`tests/test_tools.py`:
```python
import subprocess

import pytest

from composer import tools
from composer.errors import ToolError


def test_run_returns_completed_process():
    result = tools.run(["echo", "hello"])
    assert result.returncode == 0
    assert "hello" in result.stdout


def test_run_raises_tool_error_on_failure():
    with pytest.raises(ToolError) as exc:
        tools.run(["false"])
    assert "false" in str(exc.value)


def test_run_does_not_raise_when_check_false():
    result = tools.run(["false"], check=False)
    assert result.returncode != 0


def test_discover_returns_first_existing(monkeypatch):
    monkeypatch.setattr(tools.shutil, "which", lambda c: "/usr/bin/real" if c == "real" else None)
    assert tools.discover(["missing", "real"]) == "/usr/bin/real"


def test_discover_accepts_absolute_path(tmp_path, monkeypatch):
    binary = tmp_path / "tool"
    binary.write_text("")
    binary.chmod(0o755)
    monkeypatch.setattr(tools.shutil, "which", lambda c: None)
    assert tools.discover([str(binary)]) == str(binary)


def test_discover_returns_none_when_absent(monkeypatch):
    monkeypatch.setattr(tools.shutil, "which", lambda c: None)
    assert tools.discover(["nope"]) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'composer.tools'`.

- [ ] **Step 3: Write minimal implementation**

`src/composer/errors.py`:
```python
class ComposerError(Exception):
    """Base class for all composer errors."""


class ToolError(ComposerError):
    """An external tool was missing or exited nonzero."""


class FetchError(ComposerError):
    """A score could not be fetched."""


class RenderError(ComposerError):
    """A score could not be rendered to audio."""


class NormalizeError(ComposerError):
    """Loudness normalization failed."""
```

`src/composer/tools.py`:
```python
import os
import shutil
import subprocess

from composer.errors import ToolError


def discover(candidates: list[str] | tuple[str, ...]) -> str | None:
    """Return the first candidate resolvable on PATH or as an executable path."""
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess, capturing text output. Raises ToolError on nonzero when check."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise ToolError(
            f"command failed ({result.returncode}): {' '.join(cmd)}\n{result.stderr.strip()}"
        )
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tools.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/composer/errors.py src/composer/tools.py tests/test_tools.py
git commit -m "feat: add tools.run subprocess boundary and tool discovery"
```

---

### Task 4: Provenance model

**Files:**
- Create: `src/composer/provenance.py`
- Test: `tests/test_provenance.py`

- [ ] **Step 1: Write the failing test**

`tests/test_provenance.py`:
```python
from composer.provenance import Provenance


def test_vorbis_comments_include_legal_core():
    prov = Provenance(title="Gymnopedie No. 1", composer="Erik Satie")
    comments = prov.to_vorbis_comments()
    assert comments["SOURCE"] == "public-domain score"
    assert comments["RENDERED_LOCALLY"] == "true"
    assert comments["TITLE"] == "Gymnopedie No. 1"
    assert comments["ARTIST"] == "Erik Satie"


def test_vorbis_comments_omit_empty_fields():
    prov = Provenance(title="Untitled")
    comments = prov.to_vorbis_comments()
    assert "WORK" not in comments
    assert "RENDER_BACKEND" not in comments


def test_vorbis_comments_stringify_all_values():
    prov = Provenance(title="x", loudness_target=-16.0, measured_loudness=-15.7)
    comments = prov.to_vorbis_comments()
    assert comments["LOUDNESS_TARGET_LUFS"] == "-16.0"
    assert comments["MEASURED_LOUDNESS_LUFS"] == "-15.7"
    assert all(isinstance(v, str) for v in comments.values())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_provenance.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'composer.provenance'`.

- [ ] **Step 3: Write minimal implementation**

`src/composer/provenance.py`:
```python
from dataclasses import dataclass


@dataclass
class Provenance:
    # manifest stage
    title: str = ""
    composer: str | None = None
    work: str | None = None
    movement: str | None = None
    source_url: str | None = None
    # fetch stage
    score_format: str | None = None
    source_sha256: str | None = None
    fetch_date: str | None = None
    # render stage
    render_backend: str | None = None
    render_backend_version: str | None = None
    soundfont: str | None = None
    # normalize stage
    loudness_target: float | None = None
    measured_loudness: float | None = None
    # tag stage
    tool_version: str | None = None
    render_date: str | None = None

    def to_vorbis_comments(self) -> dict[str, str]:
        fields: dict[str, object | None] = {
            "TITLE": self.title,
            "ARTIST": self.composer,
            "WORK": self.work,
            "MOVEMENT": self.movement,
            "SOURCE_URL": self.source_url,
            "SCORE_FORMAT": self.score_format,
            "SOURCE_SHA256": self.source_sha256,
            "FETCH_DATE": self.fetch_date,
            "RENDER_BACKEND": self.render_backend,
            "RENDER_BACKEND_VERSION": self.render_backend_version,
            "SOUNDFONT": self.soundfont,
            "LOUDNESS_TARGET_LUFS": self.loudness_target,
            "MEASURED_LOUDNESS_LUFS": self.measured_loudness,
            "TOOL_VERSION": self.tool_version,
            "RENDER_DATE": self.render_date,
            "SOURCE": "public-domain score",
            "RENDERED_LOCALLY": "true",
        }
        return {k: str(v) for k, v in fields.items() if v is not None and v != ""}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_provenance.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/composer/provenance.py tests/test_provenance.py
git commit -m "feat: add Provenance accumulator with Vorbis comment serialization"
```

---

### Task 5: Manifest models and input handling

**Files:**
- Create: `src/composer/manifest.py`
- Test: `tests/test_manifest.py`

- [ ] **Step 1: Write the failing test**

`tests/test_manifest.py`:
```python
import pytest
from pydantic import ValidationError

from composer.manifest import Manifest, PieceEntry, from_input, load_manifest


def test_entry_requires_title_and_source_url():
    with pytest.raises(ValidationError):
        PieceEntry(source_url="http://x/score.musicxml")  # missing title


def test_resolve_applies_top_level_defaults():
    manifest = Manifest(
        loudness=-14.0,
        entries=[PieceEntry(title="A", source_url="http://x/a.musicxml")],
    )
    resolved = manifest.entries[0].resolved(manifest)
    assert resolved.loudness == -14.0


def test_resolve_prefers_entry_override():
    manifest = Manifest(
        loudness=-14.0,
        entries=[PieceEntry(title="A", source_url="http://x/a.musicxml", loudness=-20.0)],
    )
    resolved = manifest.entries[0].resolved(manifest)
    assert resolved.loudness == -20.0


def test_load_manifest_from_yaml(tmp_path):
    path = tmp_path / "m.yaml"
    path.write_text(
        "loudness: -16\n"
        "entries:\n"
        "  - title: Gymnopedie No. 1\n"
        "    composer: Erik Satie\n"
        "    source_url: http://x/gymnopedie.musicxml\n"
    )
    manifest = load_manifest(path)
    assert manifest.entries[0].title == "Gymnopedie No. 1"


def test_from_input_wraps_lone_score_file(tmp_path):
    score = tmp_path / "gymnopedie.musicxml"
    score.write_text("<score/>")
    manifest = from_input(str(score))
    assert len(manifest.entries) == 1
    assert manifest.entries[0].title == "gymnopedie"
    assert manifest.entries[0].source_url == str(score)


def test_from_input_wraps_url():
    manifest = from_input("https://example.org/satie.midi")
    assert manifest.entries[0].source_url == "https://example.org/satie.midi"
    assert manifest.entries[0].title == "satie"


def test_from_input_loads_yaml(tmp_path):
    path = tmp_path / "m.yml"
    path.write_text("entries:\n  - title: A\n    source_url: http://x/a.midi\n")
    manifest = from_input(str(path))
    assert manifest.entries[0].title == "A"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_manifest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'composer.manifest'`.

- [ ] **Step 3: Write minimal implementation**

Add `pyyaml` to deps first: edit `pyproject.toml` `dependencies` to include `"pyyaml>=6"`, then `uv sync`.

`src/composer/manifest.py`:
```python
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class PieceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    source_url: str
    composer: str | None = None
    work: str | None = None
    movement: str | None = None
    # per-entry overrides
    backend: str | None = None
    loudness: float | None = None
    soundfont: str | None = None
    out_name: str | None = None

    def resolved(self, manifest: "Manifest") -> "PieceEntry":
        """Return a copy with top-level defaults filled in where entry is unset."""
        return self.model_copy(
            update={
                "backend": self.backend or manifest.backend,
                "loudness": self.loudness if self.loudness is not None else manifest.loudness,
                "soundfont": self.soundfont or manifest.soundfont,
            }
        )


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend: str | None = None
    loudness: float | None = None
    soundfont: str | None = None
    out_dir: str | None = None
    entries: list[PieceEntry] = []


def load_manifest(path: str | Path) -> Manifest:
    data = yaml.safe_load(Path(path).read_text()) or {}
    return Manifest.model_validate(data)


def from_input(value: str) -> Manifest:
    """Accept a manifest path, a score file path, or a URL; always return a Manifest."""
    lowered = value.lower()
    if lowered.endswith((".yaml", ".yml")):
        return load_manifest(value)
    title = Path(value.split("?")[0]).stem
    return Manifest(entries=[PieceEntry(title=title, source_url=value)])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_manifest.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/composer/manifest.py tests/test_manifest.py
git commit -m "feat: add manifest models, YAML loading, and lone-input auto-wrap"
```

---

### Task 6: Fetch stage

**Files:**
- Create: `src/composer/stages/__init__.py` (empty)
- Create: `src/composer/stages/fetch.py`
- Test: `tests/stages/test_fetch.py`

- [ ] **Step 1: Write the failing test**

`tests/stages/test_fetch.py`:
```python
import hashlib

from composer.provenance import Provenance
from composer.stages.fetch import UrlFetcher


def test_fetches_and_caches_local_file(tmp_path):
    source = tmp_path / "score.musicxml"
    source.write_text("<score>hi</score>")
    cache = tmp_path / "cache"
    prov = Provenance(title="x")

    fetcher = UrlFetcher(cache_dir=cache)
    out = fetcher.fetch(str(source), prov)

    assert out.exists()
    assert out.read_text() == "<score>hi</score>"
    expected_sha = hashlib.sha256(b"<score>hi</score>").hexdigest()
    assert prov.source_sha256 == expected_sha
    assert prov.score_format == "musicxml"


def test_reuses_cache_on_second_fetch(tmp_path):
    source = tmp_path / "score.midi"
    source.write_bytes(b"MThd")
    cache = tmp_path / "cache"
    prov = Provenance(title="x")
    fetcher = UrlFetcher(cache_dir=cache)

    first = fetcher.fetch(str(source), prov)
    source.unlink()  # remove origin; cache must still satisfy the second call
    second = fetcher.fetch(str(source), Provenance(title="x"))

    assert first == second
    assert second.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/stages/test_fetch.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'composer.stages.fetch'`.

- [ ] **Step 3: Write minimal implementation**

Create empty `src/composer/stages/__init__.py` and `tests/stages/__init__.py` (empty).

`src/composer/stages/fetch.py`:
```python
import hashlib
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Protocol

from composer.errors import FetchError
from composer.provenance import Provenance

_FORMATS = {
    ".musicxml": "musicxml",
    ".xml": "musicxml",
    ".mxl": "musicxml",
    ".mid": "midi",
    ".midi": "midi",
}


def _format_for(name: str) -> str:
    suffix = Path(name.split("?")[0]).suffix.lower()
    fmt = _FORMATS.get(suffix)
    if fmt is None:
        raise FetchError(f"unsupported score format: {name!r}")
    return fmt


class Fetcher(Protocol):
    def fetch(self, url: str, prov: Provenance) -> Path: ...


class UrlFetcher:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir

    def fetch(self, url: str, prov: Provenance) -> Path:
        fmt = _format_for(url)
        key = hashlib.sha256(url.encode()).hexdigest()[:16]
        suffix = Path(url.split("?")[0]).suffix.lower()
        target = self.cache_dir / f"{key}{suffix}"

        if not target.exists():
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            data = self._read(url)
            target.write_bytes(data)

        content = target.read_bytes()
        prov.score_format = fmt
        prov.source_url = url
        prov.source_sha256 = hashlib.sha256(content).hexdigest()
        return target

    def _read(self, url: str) -> bytes:
        parsed = urllib.parse.urlparse(url)
        try:
            if parsed.scheme in ("http", "https"):
                with urllib.request.urlopen(url) as resp:  # noqa: S310 - PD score URLs only
                    return resp.read()
            local = Path(url if parsed.scheme == "" else parsed.path)
            return local.read_bytes()
        except OSError as exc:
            raise FetchError(f"could not fetch {url}: {exc}") from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/stages/test_fetch.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/composer/stages/__init__.py tests/stages/__init__.py src/composer/stages/fetch.py tests/stages/test_fetch.py
git commit -m "feat: add UrlFetcher stage with sha256 cache and format detection"
```

---

### Task 7: Render backends and selector

**Files:**
- Create: `src/composer/stages/render.py`
- Test: `tests/stages/test_render.py`

- [ ] **Step 1: Write the failing test**

`tests/stages/test_render.py`:
```python
from pathlib import Path

import pytest

from composer import tools
from composer.config import Config
from composer.errors import RenderError
from composer.provenance import Provenance
from composer.stages import render
from composer.stages.render import MuseScoreBackend, FluidSynthBackend, select_backend


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/stages/test_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'composer.stages.render'`.

- [ ] **Step 3: Write minimal implementation**

`src/composer/stages/render.py`:
```python
from pathlib import Path
from typing import Protocol

from composer import tools
from composer.config import Config
from composer.errors import RenderError
from composer.provenance import Provenance


class RenderBackend(Protocol):
    name: str

    def is_available(self) -> bool: ...
    def supports(self, source_format: str) -> bool: ...
    def render(self, score: Path, out_wav: Path, prov: Provenance) -> None: ...


class MuseScoreBackend:
    name = "musescore"
    formats = frozenset({"musicxml", "midi"})

    def __init__(self, config: Config):
        self.config = config

    def _binary(self) -> str | None:
        return tools.discover(self.config.musescore_candidates)

    def is_available(self) -> bool:
        return self._binary() is not None

    def supports(self, source_format: str) -> bool:
        return source_format in self.formats

    def render(self, score: Path, out_wav: Path, prov: Provenance) -> None:
        binary = self._binary()
        if binary is None:
            raise RenderError("MuseScore (mscore) not found")
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        tools.run([binary, "-o", str(out_wav), str(score)])
        prov.render_backend = self.name


class FluidSynthBackend:
    name = "fluidsynth"
    formats = frozenset({"midi"})

    def __init__(self, config: Config):
        self.config = config

    def _binary(self) -> str | None:
        return tools.discover(self.config.fluidsynth_candidates)

    def is_available(self) -> bool:
        return self._binary() is not None and self.config.soundfont is not None

    def supports(self, source_format: str) -> bool:
        return source_format in self.formats

    def render(self, score: Path, out_wav: Path, prov: Provenance) -> None:
        binary = self._binary()
        if binary is None:
            raise RenderError("FluidSynth not found")
        if self.config.soundfont is None:
            raise RenderError("FluidSynth backend requires a soundfont (--soundfont)")
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        tools.run([binary, "-ni", "-F", str(out_wav), str(self.config.soundfont), str(score)])
        prov.render_backend = self.name
        prov.soundfont = str(self.config.soundfont)


_BACKENDS = {"musescore": MuseScoreBackend, "fluidsynth": FluidSynthBackend}


def select_backend(config: Config, source_format: str, forced: str | None) -> RenderBackend:
    if forced is not None:
        backend = _BACKENDS[forced](config)
        if not backend.is_available():
            raise RenderError(f"forced backend {forced!r} is not available")
        if not backend.supports(source_format):
            raise RenderError(f"backend {forced!r} cannot render {source_format} input")
        return backend

    for name in config.backend_order:
        backend = _BACKENDS[name](config)
        if backend.is_available() and backend.supports(source_format):
            return backend

    raise RenderError(
        f"no available render backend supports {source_format} input "
        f"(checked: {', '.join(config.backend_order)})"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/stages/test_render.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/composer/stages/render.py tests/stages/test_render.py
git commit -m "feat: add render backends with format-aware fallback selector"
```

---

### Task 8: Normalize stage (loudnorm two-pass)

**Files:**
- Create: `src/composer/stages/normalize.py`
- Test: `tests/stages/test_normalize.py`

- [ ] **Step 1: Write the failing test**

`tests/stages/test_normalize.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/stages/test_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'composer.stages.normalize'`.

- [ ] **Step 3: Write minimal implementation**

`src/composer/stages/normalize.py`:
```python
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
        [config.ffmpeg, "-i", str(in_wav), "-af", f"{base_filter}:print_format=json", "-f", "null", "-"]
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/stages/test_normalize.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add src/composer/stages/normalize.py tests/stages/test_normalize.py
git commit -m "feat: add two-pass loudnorm normalize stage"
```

---

### Task 9: Encode stage (WAV -> OGG)

**Files:**
- Create: `src/composer/stages/encode.py`
- Test: `tests/stages/test_encode.py`

- [ ] **Step 1: Write the failing test**

`tests/stages/test_encode.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/stages/test_encode.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'composer.stages.encode'`.

- [ ] **Step 3: Write minimal implementation**

`src/composer/stages/encode.py`:
```python
from pathlib import Path

from composer import tools
from composer.config import Config


def encode(in_wav: Path, out_ogg: Path, config: Config) -> Path:
    out_ogg.parent.mkdir(parents=True, exist_ok=True)
    tools.run(
        [config.ffmpeg, "-y", "-i", str(in_wav), "-c:a", "libvorbis", "-q:a", "5", str(out_ogg)]
    )
    return out_ogg
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/stages/test_encode.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add src/composer/stages/encode.py tests/stages/test_encode.py
git commit -m "feat: add WAV-to-OGG encode stage"
```

---

### Task 10: Tag stage (provenance round-trip)

**Files:**
- Create: `src/composer/stages/tag.py`
- Test: `tests/stages/test_tag.py`

- [ ] **Step 1: Write the failing test**

`tests/stages/test_tag.py`:
```python
import shutil
import subprocess

import pytest
from mutagen.oggvorbis import OggVorbis

from composer.provenance import Provenance
from composer.stages.tag import tag

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg needed to mint a real OGG fixture"
)


@requires_ffmpeg
def test_provenance_round_trips_through_ogg(tmp_path):
    ogg = tmp_path / "track.ogg"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
         "-t", "0.1", "-c:a", "libvorbis", str(ogg)],
        check=True, capture_output=True,
    )

    prov = Provenance(
        title="Gymnopedie No. 1", composer="Erik Satie",
        render_backend="musescore", loudness_target=-16.0,
    )
    tag(ogg, prov)

    read = OggVorbis(ogg)
    assert read["SOURCE"] == ["public-domain score"]
    assert read["RENDERED_LOCALLY"] == ["true"]
    assert read["TITLE"] == ["Gymnopedie No. 1"]
    assert read["RENDER_BACKEND"] == ["musescore"]
    assert read["LOUDNESS_TARGET_LUFS"] == ["-16.0"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/stages/test_tag.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'composer.stages.tag'`.

- [ ] **Step 3: Write minimal implementation**

`src/composer/stages/tag.py`:
```python
from pathlib import Path

from mutagen.oggvorbis import OggVorbis

from composer.provenance import Provenance


def tag(ogg_path: Path, prov: Provenance) -> None:
    audio = OggVorbis(ogg_path)
    for key, value in prov.to_vorbis_comments().items():
        audio[key] = value
    audio.save()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/stages/test_tag.py -v`
Expected: PASS (1 passed) — or SKIPPED if ffmpeg is unavailable.

- [ ] **Step 5: Commit**

```bash
git add src/composer/stages/tag.py tests/stages/test_tag.py
git commit -m "feat: add provenance tagging stage with round-trip test"
```

---

### Task 11: Pipeline orchestrator

**Files:**
- Create: `src/composer/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

`tests/test_pipeline.py`:
```python
from pathlib import Path

import composer
from composer import pipeline
from composer.config import Config
from composer.manifest import Manifest, PieceEntry
from composer.provenance import Provenance


def _stub_stages(monkeypatch, fail_titles=()):
    """Replace every external stage with an in-process stub."""
    def fake_fetch(self, url, prov):
        prov.score_format = "midi"
        prov.source_sha256 = "deadbeef"
        return Path(url)

    monkeypatch.setattr(pipeline.UrlFetcher, "fetch", fake_fetch)

    class FakeBackend:
        name = "musescore"

        def render(self, score, out_wav, prov):
            prov.render_backend = "musescore"
            out_wav.parent.mkdir(parents=True, exist_ok=True)
            out_wav.write_bytes(b"WAV")

    def fake_select(config, source_format, forced):
        return FakeBackend()

    def fake_normalize(in_wav, out_wav, target_lufs, config, prov):
        prov.loudness_target = target_lufs
        out_wav.write_bytes(b"WAV")
        return out_wav

    def fake_encode(in_wav, out_ogg, config):
        out_ogg.write_bytes(b"OGG")
        return out_ogg

    def fake_tag(ogg_path, prov):
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'composer.pipeline'`.

- [ ] **Step 3: Write minimal implementation**

`src/composer/pipeline.py`:
```python
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
    raw_wav = work_dir / f"{out_name}.raw.wav"
    norm_wav = work_dir / f"{out_name}.norm.wav"
    out_ogg = config.out_dir / f"{out_name}.ogg"

    score = UrlFetcher(config.cache_dir).fetch(entry.source_url, prov)
    backend = select_backend(config, source_format=prov.score_format, forced=entry.backend)
    backend.render(score, raw_wav, prov)
    target = entry.loudness if entry.loudness is not None else config.loudness
    normalize(raw_wav, norm_wav, target_lufs=target, config=config, prov=prov)
    encode(norm_wav, out_ogg, config)

    prov.tool_version = composer.__version__
    prov.render_date = _now()
    tag(out_ogg, prov)

    return PieceResult(title=entry.title, ok=True, output_path=out_ogg, provenance=prov)


def run(manifest: Manifest, config: Config) -> Report:
    report = Report()
    for entry in manifest.entries:
        resolved = entry.resolved(manifest)
        try:
            report.results.append(run_piece(resolved, config))
        except Exception as exc:  # per-piece isolation
            report.results.append(PieceResult(title=entry.title, ok=False, error=str(exc)))
    return report
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/composer/pipeline.py tests/test_pipeline.py
git commit -m "feat: add pipeline orchestrator with per-piece isolation and report"
```

---

### Task 12: CLI

**Files:**
- Create: `src/composer/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:
```python
from pathlib import Path

from typer.testing import CliRunner

from composer import cli, pipeline
from composer.pipeline import PieceResult, Report

runner = CliRunner()


def test_render_reports_success(monkeypatch, tmp_path):
    captured = {}

    def fake_run(manifest, config):
        captured["manifest"] = manifest
        captured["config"] = config
        return Report(results=[PieceResult(title="A", ok=True, output_path=tmp_path / "A.ogg")])

    monkeypatch.setattr(cli, "run", fake_run)

    score = tmp_path / "song.midi"
    score.write_bytes(b"MThd")
    result = runner.invoke(cli.app, ["render", str(score), "--out-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "1 succeeded" in result.stdout
    assert captured["manifest"].entries[0].source_url == str(score)
    assert captured["config"].out_dir == tmp_path


def test_render_nonzero_exit_on_failure(monkeypatch, tmp_path):
    def fake_run(manifest, config):
        return Report(results=[PieceResult(title="A", ok=False, error="boom")])

    monkeypatch.setattr(cli, "run", fake_run)
    score = tmp_path / "song.midi"
    score.write_bytes(b"MThd")

    result = runner.invoke(cli.app, ["render", str(score)])

    assert result.exit_code == 1
    assert "boom" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'composer.cli'`.

- [ ] **Step 3: Write minimal implementation**

`src/composer/cli.py`:
```python
from pathlib import Path
from typing import Optional

import typer

from composer.config import Config
from composer.manifest import from_input
from composer.pipeline import run

app = typer.Typer(add_completion=False, help="Render public-domain notation into tagged audio.")


@app.command()
def render(
    input: str = typer.Argument(..., help="Manifest (.yaml) path, score file, or URL."),
    out_dir: Path = typer.Option(Path("out"), "--out-dir", help="Output directory."),
    backend: Optional[str] = typer.Option(None, "--backend", help="Force musescore|fluidsynth."),
    loudness: Optional[float] = typer.Option(None, "--loudness", help="Integrated LUFS target."),
    soundfont: Optional[Path] = typer.Option(None, "--soundfont", help="SoundFont for FluidSynth."),
) -> None:
    manifest = from_input(input)
    config = Config(out_dir=out_dir, soundfont=soundfont)
    if loudness is not None:
        config.loudness = loudness
    if backend is not None:
        manifest.backend = backend

    report = run(manifest, config)

    for result in report.results:
        if result.ok:
            typer.echo(f"  ok    {result.title} -> {result.output_path}")
        else:
            typer.echo(f"  FAIL  {result.title}: {result.error}")
    typer.echo(f"{report.succeeded} succeeded, {report.failed} failed")
    raise typer.Exit(code=report.exit_code)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the full suite and the linter**

Run: `uv run pytest -v && uv run ruff check src tests`
Expected: all tests PASS, ruff reports no errors.

- [ ] **Step 6: Commit**

```bash
git add src/composer/cli.py tests/test_cli.py
git commit -m "feat: add Typer render CLI wiring manifest to pipeline"
```

---

### Task 13: Gymnopédie end-to-end smoke test (the first win)

This is the executable form of the project's first win. It is gated on the real toolchain and skips when MuseScore/ffmpeg are absent (e.g. CI without them). It needs a real PD MusicXML URL in `tests/data/gymnopedie.manifest.yaml`.

**Files:**
- Create: `tests/data/gymnopedie.manifest.yaml`
- Create: `tests/test_integration_gymnopedie.py`

- [ ] **Step 1: Add the manifest fixture**

`tests/data/gymnopedie.manifest.yaml` (replace the URL with a verified PD MusicXML link from Mutopia/IMSLP before running):
```yaml
loudness: -16
entries:
  - title: Gymnopedie No. 1
    composer: Erik Satie
    work: Trois Gymnopedies
    movement: No. 1
    source_url: https://REPLACE-WITH-VERIFIED-PD-MUSICXML-URL/gymnopedie1.musicxml
```

- [ ] **Step 2: Write the gated integration test**

`tests/test_integration_gymnopedie.py`:
```python
import shutil
from pathlib import Path

import pytest
from mutagen.oggvorbis import OggVorbis

from composer.config import Config
from composer.manifest import load_manifest
from composer.pipeline import run

MANIFEST = Path(__file__).parent / "data" / "gymnopedie.manifest.yaml"


def _musescore_present() -> bool:
    candidates = Config().musescore_candidates
    return any(shutil.which(c) for c in candidates) or any(
        Path(c).exists() for c in candidates
    )


requires_toolchain = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or not _musescore_present(),
    reason="needs MuseScore 4 + ffmpeg installed",
)


@requires_toolchain
def test_gymnopedie_renders_to_tagged_ogg(tmp_path):
    manifest = load_manifest(MANIFEST)
    config = Config(out_dir=tmp_path / "out", cache_dir=tmp_path / "cache")

    report = run(manifest, config)

    assert report.failed == 0, [r.error for r in report.results if not r.ok]
    out = report.results[0].output_path
    assert out.exists() and out.suffix == ".ogg"

    tags = OggVorbis(out)
    assert tags["SOURCE"] == ["public-domain score"]
    assert tags["RENDERED_LOCALLY"] == ["true"]
    assert tags["RENDER_BACKEND"] == ["musescore"]
```

- [ ] **Step 3: Run it**

Run: `uv run pytest tests/test_integration_gymnopedie.py -v`
Expected: PASS if MuseScore 4 + ffmpeg are installed and the URL is valid; otherwise SKIPPED.

- [ ] **Step 4: Manual one-command verification (when toolchain present)**

Run: `uv run composer render tests/data/gymnopedie.manifest.yaml --out-dir out`
Expected: `out/Gymnopedie No. 1.ogg` exists; `1 succeeded, 0 failed` printed.
Verify tags: `uv run python -c "from mutagen.oggvorbis import OggVorbis; print(OggVorbis('out/Gymnopedie No. 1.ogg').tags)"`

- [ ] **Step 5: Commit**

```bash
git add tests/data/gymnopedie.manifest.yaml tests/test_integration_gymnopedie.py
git commit -m "test: add gated Gymnopedie end-to-end smoke test"
```

---

### Task 14: Update project docs to match reality

**Files:**
- Modify: `CLAUDE.md` (Status section)
- Modify: `README.md` (Status section + a real usage example)

- [ ] **Step 1: Update CLAUDE.md Status section**

Replace the `## Status` section with real module layout and run instructions:
```markdown
## Status

Vertical slice implemented. Module layout under `src/composer/` (stages in
`src/composer/stages/`). Install with `uv sync`; run tests with `uv run pytest`;
render with `uv run composer render <manifest|score|url> [--out-dir ...]`.
The Gymnopedie smoke test lives in `tests/test_integration_gymnopedie.py`
(gated on MuseScore 4 + ffmpeg being installed).
```

- [ ] **Step 2: Update README.md**

Replace the `## Status` section:
```markdown
## Status

🚧 Early development — single-piece and batch rendering work. First milestone
(render Satie's *Gymnopédie No. 1* to a tagged OGG in one command) is wired and
covered by a gated integration test.

## Usage

```bash
uv sync
uv run composer render path/to/score.musicxml --out-dir out
uv run composer render manifest.yaml --out-dir out   # batch
```
```

- [ ] **Step 3: Verify docs build/read correctly**

Run: `uv run pytest -q`
Expected: full suite green (integration test skipped without toolchain).

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: update status and usage to reflect implemented pipeline"
```

---

## Notes for the executor

- Run every command from the repo root with `uv run ...`.
- The branch is `feat/pipeline-architecture-spec`; commits to `main` are blocked by a hook.
- The only mocking boundary is `composer.tools.run` (and `discover`) plus the stage functions in pipeline tests. Never mock deeper than that.
- Tasks 1–12 are fully offline and require no external audio tools. Tasks 10 and 13 use ffmpeg / MuseScore and skip when absent.
- Before running Task 13, replace the placeholder URL in the manifest fixture with a verified public-domain MusicXML link.
