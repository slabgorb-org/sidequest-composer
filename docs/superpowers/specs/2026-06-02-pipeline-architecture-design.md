# sidequest-composer — Pipeline Architecture Design

**Date:** 2026-06-02
**Status:** Approved design, pre-implementation

## Summary

A local, offline CLI that turns public-domain sheet music (MusicXML/MIDI) into
clean, rights-free audio tracks. The *composition* is public domain but every
*recording* is copyrighted — so we skip the recording and render fresh audio
from the notation. The output is unencumbered by construction (the performance
was generated locally), with provenance baked into the artifact's tags.

This is **deterministic synthesis from notation, not AI generation.**

This document designs the **full pipeline architecture**. It is intended to be
implemented in milestones, with the first milestone being the single-piece
vertical slice (the Gymnopédie smoke test).

## Scope

**In scope:** manifest-driven fetch → render → normalize → encode → tag →
export, with batch as a first-class path and single-file as the degenerate
case.

**Out of scope (do not build):** no DAW, no mixing UI, no original composition,
no AI generation of any kind, no accounts/licenses/network services beyond
downloading PD scores from URLs the user/manifest supplies.

## Decisions

These were settled during brainstorming and drive the design:

1. **Session scope:** design the full pipeline architecture; implement in
   milestones (vertical slice first).
2. **Fetch model:** manifest with **direct URLs**. The manifest provides
   download URLs to MusicXML/MIDI files plus metadata. No scraping, no live
   search. Composer/work/movement are metadata fields, not a search query.
3. **Render backend selection:** **MuseScore 4 by default, automatic fallback**
   to FluidSynth+SoundFont if MuseScore is missing or fails. `--backend` forces
   one with no fallback. The fallback is *reported*, never silent, and the real
   backend used is recorded in provenance.
4. **Provenance:** **rich, structured provenance** embedded in the audio tags
   (Vorbis comments for OGG). Records source, render backend+version, soundfont,
   loudness target, tool version, dates, checksums.
5. **Output:** **OGG Vorbis at -16 LUFS** integrated by default; WAV available
   via flag; loudness target overridable via flag/manifest.
6. **CLI surface:** **single command + manifest.** The manifest is the universal
   input; one entry = single render, many = batch. A lone score file or URL is
   auto-wrapped into a one-entry manifest so the smoke test is genuinely one
   command.
7. **Pipeline structure:** **explicit named stages + a thin orchestrator**
   (approach C). `Protocol` seams only for the render backend (mandated by
   CLAUDE.md) and the fetcher; every other stage stays concrete.

## Architecture & module layout

```
composer/
  cli.py            # Typer entry: `composer render <input> [opts]`
  manifest.py       # load + validate YAML; PieceEntry model; auto-wrap lone score file
  pipeline.py       # Pipeline runner: orders stages, per-piece isolation, builds report
  provenance.py     # Provenance accumulator model + serialization
  stages/
    fetch.py        # Fetcher Protocol; UrlFetcher (download -> cache by checksum)
    render.py       # RenderBackend Protocol; MuseScoreBackend, FluidSynthBackend; selector w/ fallback
    normalize.py    # ffmpeg loudnorm (two-pass) -> normalized WAV
    encode.py       # ffmpeg WAV -> OGG Vorbis
    tag.py          # write provenance as Vorbis comments (mutagen)
  tools.py          # subprocess wrappers + tool discovery/version probing
  config.py         # defaults: backend order, -16 LUFS, out dir, soundfont path
```

Each stage is a function with explicit, typed inputs and outputs (not one shared
mutable blob threaded everywhere). `RenderBackend` and `Fetcher` are the only
`Protocol` seams — the points where CLAUDE.md requires swappability and where a
genuine alternative implementation is plausible. Keeping the rest concrete keeps
the flow readable and each unit independently testable, which matters because
every stage shells out to a different external tool.

## Data flow

The manifest is the universal input. A bare `score.musicxml` or a URL passed on
the CLI is auto-wrapped into a one-entry manifest.

```
manifest.yaml --> [PieceEntry] --+   (one entry = single render; many = batch)
                                 |
   per piece:                    v
   fetch --> render --> normalize --> encode --> tag --> output.ogg + report row
   (URL->     (->raw    (loudnorm      (->OGG     (write
    cache)     WAV)      2-pass->WAV)   Vorbis)    provenance)
```

Stages and their transformations:

| Stage | Input | Output | External tool |
|-------|-------|--------|---------------|
| fetch | source URL | cached score file (MusicXML/MIDI) | none (HTTP download) |
| render | score file | raw WAV | `mscore` or `fluidsynth` |
| normalize | raw WAV | normalized WAV | `ffmpeg` loudnorm + `ffprobe` |
| encode | normalized WAV | OGG Vorbis | `ffmpeg` |
| tag | OGG + Provenance | tagged OGG | `mutagen` (library) |

### Provenance accumulator

A `Provenance` object is created per piece and accumulates as it flows. Each
stage stamps what it knows:

| Stage | Stamps |
|-------|--------|
| manifest | composer, work, movement, title, source URL |
| fetch | score format, fetched-file SHA-256, fetch date |
| render | backend used (musescore/fluidsynth) + version, soundfont (if used) |
| normalize | loudness target (-16 LUFS), measured integrated loudness |
| tag | tool version, render date, `source=public-domain score`, `rendered-locally=true` |

At the tag stage the whole object is written as Vorbis comments on the OGG.
Because the render fallback is reported, the **actual** backend used is what
gets recorded — the artifact never misrepresents how it was made. Provenance is
a product feature (the legal value proposition), not metadata hygiene, and must
never be dropped.

### Manifest schema

Per entry:

- `title` — **required**
- `source_url` — **required** (direct download URL to MusicXML/MIDI)
- `composer`, `work`, `movement` — metadata (recorded in provenance)
- Optional per-entry overrides: `backend`, `loudness`, `soundfont`, `out_name`

Top-level keys provide defaults applied to all entries (e.g. default `out_dir`,
`loudness`, `backend`). Per-entry values override top-level defaults.

The CLI also accepts a lone score file path or URL, which `manifest.py`
auto-wraps into a single `PieceEntry` (using the filename as the title) so a
one-piece render needs no manifest file.

## Error handling & determinism

- **Per-piece isolation (batch):** a piece failing (bad URL, unrenderable
  score, encode error) logs the error, records a failed row in the report, and
  the run continues to the next piece. The process exit code reflects whether
  any piece failed. A summary report (N succeeded / M failed, with reasons)
  prints at the end of the run.
- **Render fallback:** MuseScore is tried first. If `mscore` is missing or exits
  nonzero, fall back to FluidSynth, emit a visible warning, and record the real
  backend in provenance. `--backend` forces a single backend with **no**
  fallback — a forced backend that fails is a hard error.
- **Missing tools:** `tools.py` probes tool availability up front. Absence of
  *all* render backends, or of `ffmpeg`, is a clear hard error naming the
  missing tool and how to install it — not a stack trace.
- **Determinism / caching:** fetched scores are cached to disk and verified by
  SHA-256, so re-runs are offline and reproducible. Renders are reproducible
  given the same backend + version, both of which are recorded in provenance.

## Testing strategy

- **Stage unit tests:** each stage tested with its external tool mocked at the
  `tools.py` subprocess boundary — assert the correct command and arguments are
  constructed (e.g. loudnorm runs a measurement pass then an apply pass; the
  encoder targets OGG Vorbis).
- **Provenance round-trip:** write tags to a real OGG file, read them back with
  mutagen, and assert every field survives. This is the regression guard for the
  legal feature.
- **Manifest validation:** good and bad manifests, the lone-file auto-wrap
  behavior, and per-entry override merging against top-level defaults.
- **Batch isolation:** a manifest containing one deliberately-failing entry
  proves the run completes, other entries still render, and the report is
  accurate.
- **Real integration smoke test:** the Gymnopédie No. 1 end-to-end render
  (manifest → tagged OGG), gated behind a check that the real tools
  (`mscore`/`fluidsynth`, `ffmpeg`) are installed; skipped where they are not
  (e.g. CI without the toolchain). This is the executable form of the project's
  "first win."

## Tooling choices

- **Language:** Python.
- **CLI:** Typer.
- **Manifest models/validation:** pydantic (typed `PieceEntry` and manifest
  models).
- **Tag read/write:** mutagen (robust Vorbis-comment support).
- **Subprocess & caching:** stdlib `subprocess` and `hashlib`.
- **Loudness measurement:** `ffprobe` (alongside `ffmpeg` loudnorm).

All renderers and ffmpeg are invoked as external subprocesses, never as Python
libraries, per CLAUDE.md.

## Implementation milestones

1. **Vertical slice (first win):** single-piece path — manifest (or lone file) →
   fetch → MuseScore render → loudnorm → OGG encode → provenance tags. Prove
   Gymnopédie No. 1 renders to a tagged OGG in one command.
2. **Backend abstraction & fallback:** add the FluidSynth backend behind the
   `RenderBackend` protocol and the MuseScore-default auto-fallback selector.
3. **Batch mode:** multi-entry manifests, per-piece isolation, summary report.
4. **Hardening:** richer provenance fields, configurable loudness/output,
   tool-discovery error messages, caching.
