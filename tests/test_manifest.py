import pytest
from pydantic import ValidationError

from composer.manifest import Manifest, PieceEntry, from_input, load_manifest


def test_entry_requires_title_and_source_url():
    with pytest.raises(ValidationError):
        PieceEntry(source_url="http://x/score.musicxml")  # missing title


def test_resolve_applies_top_level_defaults():
    manifest = Manifest(
        loudness=-14.0,
        entries=[PieceEntry(title="A", source_url="http://x/a.musicxml")],
    )
    resolved = manifest.entries[0].resolved(manifest)
    assert resolved.loudness == -14.0


def test_resolve_prefers_entry_override():
    manifest = Manifest(
        loudness=-14.0,
        entries=[PieceEntry(title="A", source_url="http://x/a.musicxml", loudness=-20.0)],
    )
    resolved = manifest.entries[0].resolved(manifest)
    assert resolved.loudness == -20.0


def test_load_manifest_from_yaml(tmp_path):
    path = tmp_path / "m.yaml"
    path.write_text(
        "loudness: -16\n"
        "entries:\n"
        "  - title: Gymnopedie No. 1\n"
        "    composer: Erik Satie\n"
        "    source_url: http://x/gymnopedie.musicxml\n"
    )
    manifest = load_manifest(path)
    assert manifest.entries[0].title == "Gymnopedie No. 1"


def test_from_input_wraps_lone_score_file(tmp_path):
    score = tmp_path / "gymnopedie.musicxml"
    score.write_text("<score/>")
    manifest = from_input(str(score))
    assert len(manifest.entries) == 1
    assert manifest.entries[0].title == "gymnopedie"
    assert manifest.entries[0].source_url == str(score)


def test_from_input_wraps_url():
    manifest = from_input("https://example.org/satie.midi")
    assert manifest.entries[0].source_url == "https://example.org/satie.midi"
    assert manifest.entries[0].title == "satie"


def test_from_input_loads_yaml(tmp_path):
    path = tmp_path / "m.yml"
    path.write_text("entries:\n  - title: A\n    source_url: http://x/a.midi\n")
    manifest = from_input(str(path))
    assert manifest.entries[0].title == "A"
