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
