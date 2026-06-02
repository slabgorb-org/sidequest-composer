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
