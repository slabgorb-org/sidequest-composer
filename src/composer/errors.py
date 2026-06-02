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
