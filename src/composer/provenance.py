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
