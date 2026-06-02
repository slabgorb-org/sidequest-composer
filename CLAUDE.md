# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local, offline CLI that turns **public-domain sheet music** (MusicXML/MIDI) into clean, **rights-free audio tracks**. The core thesis: the *composition* is public domain but every *recording* is copyrighted — so skip the recording entirely and render fresh audio from the notation. The output is unencumbered by construction (you generated the performance locally), not licensed.

This is **deterministic synthesis from notation, not AI generation**. Notation in → audio out.

## The pipeline (core mental model)

The whole tool is one data flow. Understanding it is understanding the codebase:

```
piece list / manifest  ──►  fetch PD score        (IMSLP / Mutopia)   ─┐
MusicXML / MIDI file   ──►  (or take user's file)                      ├─►  render audio   ──►  normalize loudness  ──►  tag + export
                                                                       ┘    (MuseScore 4 CLI    (ffmpeg / loudnorm)     (OGG/WAV w/ provenance)
                                                                             or FluidSynth+SF2)
```

Every stage is a swappable unit. The two rendering backends (MuseScore 4 `mscore -o` and FluidSynth + SoundFont) must be interchangeable behind one interface — keep render logic backend-agnostic above that boundary.

**Provenance is a product feature, not metadata hygiene.** Exported files must carry tags recording that the source was a PD score and that audio was rendered locally. This is the legal value proposition baked into the artifact — never drop it.

## Toolchain (external dependencies)

These are CLI tools invoked as subprocesses, not Python libraries:

- **MuseScore 4** — `mscore -o output.wav input.musicxml` (primary backend; MuseSounds quality is the differentiator)
- **FluidSynth + SoundFont (.sf2)** — fallback / alternative render backend
- **ffmpeg** — loudness normalization (`loudnorm`) and OGG/WAV export
- Score sources: **IMSLP**, **Mutopia** (MusicXML/MIDI, public domain)

Stack: Python CLI orchestrating the above. Mac-native, fully offline, scriptable.

## Scope discipline (read before adding features)

Deliberately **out of scope** — do not build these, and push back if asked to drift toward them:
- No DAW, no mixing UI
- No original composition
- **No AI generation** of any kind
- No accounts, licenses, or network services beyond fetching PD scores

The constraint *is* the design. Keep it small: notation in, audio out.

## Priorities

- **Solo piano renders beautifully; orchestral is "serviceable at background volume."** Lead with and prioritize piano repertoire — that's where the demo sings.
- **First win / smoke test of the whole thesis:** render Satie's Gymnopédie No. 1 from a Mutopia MusicXML to a tagged OGG in **one command**. If that works end-to-end, the architecture is sound.
- **Batch mode** is a first-class path: feed a manifest, get a folder of named tracks. Single-file rendering is the degenerate case of batch.

## Status

Greenfield — no implementation code committed yet. This document describes intended architecture; update it as real commands, module layout, and test instructions land.
