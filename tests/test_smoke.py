import composer


def test_version_is_exposed():
    assert composer.__version__ == "0.1.0"
