import pytest

from composer import tools
from composer.errors import ToolError


def test_run_returns_completed_process():
    result = tools.run(["echo", "hello"])
    assert result.returncode == 0
    assert "hello" in result.stdout


def test_run_raises_tool_error_on_failure():
    with pytest.raises(ToolError) as exc:
        tools.run(["false"])
    assert "false" in str(exc.value)


def test_run_does_not_raise_when_check_false():
    result = tools.run(["false"], check=False)
    assert result.returncode != 0


def test_discover_returns_first_existing(monkeypatch):
    monkeypatch.setattr(tools.shutil, "which", lambda c: "/usr/bin/real" if c == "real" else None)
    assert tools.discover(["missing", "real"]) == "/usr/bin/real"


def test_discover_accepts_absolute_path(tmp_path, monkeypatch):
    binary = tmp_path / "tool"
    binary.write_text("")
    binary.chmod(0o755)
    monkeypatch.setattr(tools.shutil, "which", lambda c: None)
    assert tools.discover([str(binary)]) == str(binary)


def test_discover_returns_none_when_absent(monkeypatch):
    monkeypatch.setattr(tools.shutil, "which", lambda c: None)
    assert tools.discover(["nope"]) is None
