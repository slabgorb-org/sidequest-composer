from pathlib import Path
from typing import Optional

import typer

from composer.config import Config
from composer.manifest import from_input
from composer.pipeline import run
from composer.stages.encode import SUPPORTED_FORMATS
from composer.tools import resolve_ffmpeg_tools

app = typer.Typer(add_completion=False, help="Render public-domain notation into tagged audio.")


@app.callback()
def _main() -> None:
    """Render public-domain notation into tagged audio."""


@app.command()
def render(
    input: str = typer.Argument(..., help="Manifest (.yaml) path, score file, or URL."),
    out_dir: Path = typer.Option(Path("out"), "--out-dir", help="Output directory."),
    backend: Optional[str] = typer.Option(None, "--backend", help="Force musescore|fluidsynth."),
    loudness: Optional[float] = typer.Option(None, "--loudness", help="Integrated LUFS target."),
    soundfont: Optional[Path] = typer.Option(None, "--soundfont", help="SoundFont for FluidSynth."),
    output_format: str = typer.Option(
        "ogg", "--format", help="Output audio format: ogg|mp3|wav."
    ),
) -> None:
    if output_format not in SUPPORTED_FORMATS:
        typer.echo(f"unknown --format {output_format!r} (choose {'|'.join(SUPPORTED_FORMATS)})")
        raise typer.Exit(code=2)
    manifest = from_input(input)
    ffmpeg, ffprobe = resolve_ffmpeg_tools()
    config = Config(
        out_dir=out_dir,
        soundfont=soundfont,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
        output_format=output_format,
    )
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
