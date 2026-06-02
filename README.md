# sidequest-composer

A local CLI that turns public-domain sheet music into clean, rights-free audio tracks — no recordings, no licenses, no accounts.

## The problem

Everyone who needs background classical music — game devs, video editors, podcasters — hits the same wall: the *composition* is public domain, but every *recording* is copyrighted. So you either pay, hunt grab-bag archives of dubious provenance, or risk a takedown.

## The insight

Skip the recording entirely. The score is public domain and freely available (IMSLP, Mutopia) as MusicXML/MIDI. Render audio from the notation and the output is unencumbered **by construction** — you generated a fresh performance locally, so it's yours, free and clear.

This is **deterministic synthesis from notation, not AI generation.**

## What it does

- **Input:** a piece list (composer / work / movement) or a MusicXML/MIDI file.
- Fetches the public-domain score (or takes yours), renders to audio via MuseScore 4 CLI (or FluidSynth + SoundFont), normalizes loudness, and exports a tagged OGG/WAV with provenance baked in (`source=PD score`, `rendered locally`).
- **Batch mode:** feed it a manifest, get a folder of named tracks.

## Why local

Mac-native, free toolchain, fully offline, deterministic, and scriptable. MuseScore 4's MuseSounds are genuinely good now.

## Toolchain

These are external CLI tools the project drives as subprocesses:

| Tool | Role |
|------|------|
| [MuseScore 4](https://musescore.org) (`mscore`) | Primary render backend — `mscore -o out.wav in.musicxml` |
| [FluidSynth](https://www.fluidsynth.org) + SoundFont (`.sf2`) | Alternative / fallback render backend |
| [ffmpeg](https://ffmpeg.org) | Loudness normalization (`loudnorm`) and OGG/WAV export |

Score sources: [IMSLP](https://imslp.org), [Mutopia Project](https://www.mutopiaproject.org).

## Status

🚧 Early development. The first milestone: render Satie's *Gymnopédie No. 1* from a Mutopia MusicXML to a tagged OGG in one command.

## Scope

Intentionally small — notation in, audio out. **Out of scope:** no DAW, no mixing UI, no original composition, no AI generation, no accounts or licenses.

## License

No license is granted at this time — all rights reserved while the project's status is being decided.

Note: this concerns the *code* only. Audio you render from public-domain scores is yours by construction — the tool adds no license encumbrance to its output.
