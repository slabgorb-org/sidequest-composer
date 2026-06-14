# Spec: OMR `transcribe` stage — PDF sheet music → MusicXML → render

**Status:** proposed (parked 2026-06-14). Authored by GM after a feasibility probe.
**Lane:** Dev (Python, `sidequest-composer`). GM scoped it; GM does not implement code.

## Motivation

The composer renders public-domain *notation* (MIDI/MusicXML) to rights-free OGG.
Today the only fetchable clean-PD notation we use is Mutopia's Joplin set
(`sidequest-content/.../assets/audio/ragtime_pd/catalog.yaml`). Mutopia has
**only** Joplin among ragtime composers (probed 2026-06-14: `JoplinS` 200;
`ScottJ`/`LambJ`/`ConfreyZ` all 404). The far larger supply of PD notation lives
on **IMSLP as PDF**. An OMR (Optical Music Recognition) front stage would convert
PDF → MusicXML and feed the existing pipeline, unlocking that supply.

## Stage contract

Add a `transcribe` stage *before* `render` in `pipeline.py`:

```
fetch → [transcribe (NEW)] → render → normalize → tag → encode
```

- Input: a `.pdf` source (or image). Output: a `.musicxml` handed to `render`.
- **Source-first rule (No Silent Fallbacks):** if the catalog entry's IMSLP work
  page also offers native notation (`.mxl`/`.musicxml`/`.mid`/LilyPond `.ly`),
  prefer that — it is perfect fidelity, no OMR. OMR is the fallback for
  PDF-only works. Encode this as an explicit per-entry choice, not a guess.
- Per-entry manifest fields already flow through (`PieceEntry` has `backend`,
  `soundfont`, etc. via `{**entry}` in `render_pd_audio.py:_composer_entries`);
  add a `transcribe:` / `source_format: pdf` field in the same spirit.

## Tool choice: Audiveris (not oemer)

Probe (2026-06-14) on a **clean born-digital** engraving, via **oemer** (the
only OMR standable-up without a JDK):

| Element | Truth | oemer | 
|---|---|---|
| grand staff / clefs (G2+F4) | yes | ✅ |
| key signature | C minor (−3, three flats) | **+3 (three sharps)** ❌ sign flipped |
| measures on p.1 | 16 | **11** ❌ ~30% dropped |
| time signature | 4/4 | not emitted ⚠️ |
| flat accidentals on notes | E♭/B♭/A♭ | captured ✅ |

Conclusion: oemer gets gross structure but makes **render-breaking** errors
(key-sig sign, dropped bars) even on clean input — it needs a heavy proofing
pass, defeating the point. oemer is also unmaintained against modern numpy
(`np.int`/`np.float` removed; had to patch to run).

**Use Audiveris** (Java, GPL) — the standard for *engraved* scores, materially
better than oemer on clean typeset PDFs, which is exactly the input class here.
Integration: subprocess (`audiveris -batch -export -output <dir> <pdf>` → `.mxl`).
Requires a bundled/`discover`ed JRE 17/21, same pattern as `tools.discover` for
mscore/ffmpeg. Re-probe with Audiveris before committing — expect near-clean on
born-digital input, but still gate on a human proofing step.

## Rights gate (load-bearing — do not skip)

**"On IMSLP" ≠ "public domain."** IMSLP hosts both PD works and modern,
copyrighted, composer-submitted works. The probe specimen
(`A Walk in C Minor`, Richard P. Geere) is **© 2021** — clean, OMR-friendly, and
**unusable as content.** Worse, there is a correlation trap: *clean born-digital
PDFs skew modern/copyrighted*; the genuinely-PD 1920s ragtime skews *old scans*
(OMR's worst case). The rights-clean sweet spot is **a modern re-engraving of a
pre-1930 work with a permissive per-file license.**

The `transcribe` stage (or the catalog-authoring step) MUST record and vet:
1. **Composition** PD (first published ≤ current year − 96; ≤1930 in 2026), AND
2. **File license** — IMSLP tags every file's copyright status; CC-BY is usable
   with attribution, **CC-BY-NC is off-limits** (treat the game as commercial),
   all-rights-reserved is off-limits.

Mirror the discipline already in
`assets/audio/jazz_pd/jazz_pd_backlog.md` (verify the actual year; metadata is
not authoritative) and `PURCHASED_AUDIO.md` (provenance ledger).

## Out of scope / notes

- Combo/big-band jazz is not fetchable as clean PD MusicXML and renders poorly
  regardless (improvised, not notated). The composer's jazz value is **piano**
  ragtime/stride/novelty (Confrey, James Scott, Joseph Lamb — all PD).
- Soundfont: composer renders via the `mscore` CLI, which uses MS Basic (GM),
  **not** MuseScore's premium Muse Sounds (CLI export can't reach MuseSampler).
  `fluidsynth` is now installed; for brass-forward material, wire FluidSynth +
  a permissively-licensed orchestral `.sf2` via the per-entry `soundfont:` field.
  Irrelevant for piano ragtime (MS Basic piano is fine).
```
