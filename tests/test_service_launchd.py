from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# The launchd backend builds its service target from os.getuid(), which does not
# exist on Windows — skip the whole module there.
pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="launchd / os.getuid() is Unix-only"
)

from opengeneral import service_launchd


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("shutil.which", lambda name: "/bin/launchctl" if name == "launchctl" else None)
    return tmp_path / "Library" / "LaunchAgents"


def _scripted_launchctl(
    monkeypatch: pytest.MonkeyPatch, script: dict[str, tuple[int, str]] | None = None
) -> list[list[str]]:
    """Patch subprocess.run with a scripted launchctl keyed on the subcommand verb
    (`launchctl <verb> ...`). Also stubs shutil.which so the tests run on non-macOS hosts."""
    calls: list[list[str]] = []
    plan = script or {}

    monkeypatch.setattr("shutil.which", lambda name: "/bin/launchctl" if name == "launchctl" else None)

    def _run(cmd, capture_output, text, check):  # noqa: ANN001
        calls.append(list(cmd))
        verb = cmd[1]  # ["launchctl", <verb>, ...]
        returncode, stdout = plan.get(verb, (0, ""))
        return subprocess.CompletedProcess(cmd, returncode, stdout, "")

    monkeypatch.setattr("subprocess.run", _run)
    return calls


def test_plist_content_includes_label_and_program_args() -> None:
    content = service_launchd.plist_content()

    assert f"<string>{service_launchd.LABEL}</string>" in content
    assert f"<string>{sys.executable}</string>" in content
    assert "<key>KeepAlive</key>" in content
    assert "<key>Crashed</key>" in content


def test_install_writes_plist_and_bootstraps(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _scripted_launchctl(monkeypatch)

    result = service_launchd.install()

    plist = isolated_home / f"{service_launchd.LABEL}.plist"
    assert plist.exists()
    assert service_launchd.LABEL in plist.read_text(encoding="utf-8")
    assert any(call[1] == "bootstrap" for call in calls)
    assert "Installed launchd user agent" in result


def test_install_rolls_back_when_bootstrap_fails(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scripted_launchctl(monkeypatch, {"bootstrap": (1, "Bootstrap failed: 5: Input/output error")})

    with pytest.raises(RuntimeError, match="bootstrap.*failed"):
        service_launchd.install()

    plist = isolated_home / f"{service_launchd.LABEL}.plist"
    assert not plist.exists()


def test_install_restores_previous_plist_when_bootstrap_fails(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolated_home.mkdir(parents=True, exist_ok=True)
    plist = isolated_home / f"{service_launchd.LABEL}.plist"
    plist.write_text("previous content", encoding="utf-8")
    _scripted_launchctl(monkeypatch, {"bootstrap": (1, "Bootstrap failed")})

    with pytest.raises(RuntimeError, match="bootstrap.*failed"):
        service_launchd.install()

    assert plist.read_text(encoding="utf-8") == "previous content"


def test_uninstall_removes_plist_and_boots_out(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolated_home.mkdir(parents=True, exist_ok=True)
    plist = isolated_home / f"{service_launchd.LABEL}.plist"
    plist.write_text("stub", encoding="utf-8")
    calls = _scripted_launchctl(monkeypatch)

    result = service_launchd.uninstall()

    assert not plist.exists()
    assert any(call[1] == "bootout" for call in calls)
    assert "Uninstalled launchd user agent" in result


def test_start_when_stopped_kickstarts(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _scripted_launchctl(monkeypatch, {"list": (0, "{\n\t\"Label\" = \"x\";\n}")})

    result = service_launchd.start()

    assert any(call[1] == "kickstart" for call in calls)
    assert result == "Started OpenGeneral daemon"


def test_start_when_running_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _scripted_launchctl(monkeypatch, {"list": (0, "{\n\t\"PID\" = 4321;\n}")})

    result = service_launchd.start()

    assert result == "OpenGeneral daemon already running"
    assert not any(call[1] == "kickstart" for call in calls)


def test_status_running_when_pid_present(monkeypatch: pytest.MonkeyPatch) -> None:
    _scripted_launchctl(monkeypatch, {"list": (0, "{\n\t\"PID\" = 4321;\n}")})

    assert service_launchd.status() == "OpenGeneral daemon: running"


def test_status_stopped_when_loaded_without_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    _scripted_launchctl(monkeypatch, {"list": (0, "{\n\t\"Label\" = \"x\";\n}")})

    assert service_launchd.status() == "OpenGeneral daemon: stopped"


def test_status_not_installed_when_list_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _scripted_launchctl(monkeypatch, {"list": (113, "Could not find service")})

    assert service_launchd.status() == "OpenGeneral daemon: not installed"


def test_launchctl_missing_raises_with_foreground_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: None)

    with pytest.raises(RuntimeError, match="foreground"):
        service_launchd.start()
