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
