from composer.provenance import Provenance


def test_vorbis_comments_include_legal_core():
    prov = Provenance(title="Gymnopedie No. 1", composer="Erik Satie")
    comments = prov.to_vorbis_comments()
    assert comments["SOURCE"] == "public-domain score"
    assert comments["RENDERED_LOCALLY"] == "true"
    assert comments["TITLE"] == "Gymnopedie No. 1"
    assert comments["ARTIST"] == "Erik Satie"


def test_vorbis_comments_omit_empty_fields():
    prov = Provenance(title="Untitled")
    comments = prov.to_vorbis_comments()
    assert "WORK" not in comments
    assert "RENDER_BACKEND" not in comments


def test_vorbis_comments_stringify_all_values():
    prov = Provenance(title="x", loudness_target=-16.0, measured_loudness=-15.7)
    comments = prov.to_vorbis_comments()
    assert comments["LOUDNESS_TARGET_LUFS"] == "-16.0"
    assert comments["MEASURED_LOUDNESS_LUFS"] == "-15.7"
    assert all(isinstance(v, str) for v in comments.values())
