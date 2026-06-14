from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from opengeneral import service_systemd


@pytest.fixture
def isolated_unit_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    unit_dir = tmp_path / "systemd-system"
    monkeypatch.setattr(service_systemd, "SYSTEM_UNIT_DIR", unit_dir)
    monkeypatch.setattr(
        "shutil.which", lambda name: "/usr/bin/systemctl" if name == "systemctl" else None
    )
    return unit_dir


def _scripted_systemctl(
    monkeypatch: pytest.MonkeyPatch, script: dict[str, tuple[int, str]] | None = None
) -> list[list[str]]:
    """Patch subprocess.run with a scripted systemctl (system, not --user) keyed on
    the subcommand verb. Also stubs shutil.which so the tests run on hosts with no
    systemctl (macOS/Windows)."""
    calls: list[list[str]] = []
    plan = script or {}

    monkeypatch.setattr(
        "shutil.which", lambda name: "/usr/bin/systemctl" if name == "systemctl" else None
    )

    def _run(cmd, capture_output, text, check):  # noqa: ANN001
        calls.append(list(cmd))
        verb = cmd[1]  # ["systemctl", <verb>, ...]
        returncode, stdout = plan.get(verb, (0, ""))
        return subprocess.CompletedProcess(cmd, returncode, stdout, "")

    monkeypatch.setattr("subprocess.run", _run)
    return calls


@pytest.fixture
def fake_systemctl(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    return _scripted_systemctl(monkeypatch, {"is-active": (0, "inactive\n")})


def test_unit_runs_least_privilege_with_machine_state() -> None:
    content = service_systemd.unit_content()

    assert "[Service]" in content
    assert f"ExecStart={service_systemd.daemon_command()}" in content
    assert "DynamicUser=yes" in content
    assert f"StateDirectory={service_systemd.STATE_DIRECTORY_NAME}" in content
    assert f"Environment=OPENGENERAL_HOME={service_systemd.MACHINE_HOME}" in content
    assert "WantedBy=multi-user.target" in content
    assert "RestartPreventExitStatus=78" in content


def test_daemon_command_uses_module_form_in_source_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert service_systemd.daemon_command() == f"{sys.executable} -m opengeneral.daemon"


def test_daemon_command_uses_subcommand_form_when_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    assert service_systemd.daemon_command() == f"{sys.executable} daemon run"


def test_install_writes_unit_and_enables(isolated_unit_dir: Path, fake_systemctl: list[list[str]]) -> None:
    result = service_systemd.install()

    unit_path = isolated_unit_dir / service_systemd.SERVICE_NAME
    assert unit_path.exists()
    assert "DynamicUser=yes" in unit_path.read_text(encoding="utf-8")
    assert ["systemctl", "daemon-reload"] in fake_systemctl
    assert ["systemctl", "enable", service_systemd.SERVICE_NAME] in fake_systemctl
    assert "Installed systemd service" in result


def test_install_rolls_back_when_enable_fails(
    isolated_unit_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scripted_systemctl(
        monkeypatch,
        {"daemon-reload": (0, ""), "enable": (1, ""), "is-active": (0, "inactive\n")},
    )

    with pytest.raises(RuntimeError, match="enable.*failed"):
        service_systemd.install()

    unit_path = isolated_unit_dir / service_systemd.SERVICE_NAME
    assert not unit_path.exists()


def test_install_restores_previous_unit_when_enable_fails(
    isolated_unit_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolated_unit_dir.mkdir(parents=True, exist_ok=True)
    unit_path = isolated_unit_dir / service_systemd.SERVICE_NAME
    unit_path.write_text("previous content", encoding="utf-8")

    _scripted_systemctl(
        monkeypatch,
        {"daemon-reload": (0, ""), "enable": (1, ""), "is-active": (0, "inactive\n")},
    )

    with pytest.raises(RuntimeError, match="enable.*failed"):
        service_systemd.install()

    assert unit_path.read_text(encoding="utf-8") == "previous content"


def test_uninstall_removes_unit_and_disables(isolated_unit_dir: Path, fake_systemctl: list[list[str]]) -> None:
    isolated_unit_dir.mkdir(parents=True, exist_ok=True)
    unit_path = isolated_unit_dir / service_systemd.SERVICE_NAME
    unit_path.write_text("stub", encoding="utf-8")

    result = service_systemd.uninstall()

    assert not unit_path.exists()
    assert ["systemctl", "disable", "--now", service_systemd.SERVICE_NAME] in fake_systemctl
    assert "Uninstalled systemd service" in result


def test_start_when_inactive_invokes_systemctl_start(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _scripted_systemctl(monkeypatch, {"is-active": (0, "inactive\n")})

    result = service_systemd.start()

    assert calls[0] == ["systemctl", "is-active", service_systemd.SERVICE_NAME]
    assert ["systemctl", "start", service_systemd.SERVICE_NAME] in calls
    assert result == "Started OpenGeneral daemon"


def test_start_when_already_active_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _scripted_systemctl(monkeypatch, {"is-active": (0, "active\n")})

    result = service_systemd.start()

    assert result == "OpenGeneral daemon already running"
    assert ["systemctl", "start", service_systemd.SERVICE_NAME] not in calls


def test_status_normalizes_active_to_running(monkeypatch: pytest.MonkeyPatch) -> None:
    _scripted_systemctl(monkeypatch, {"is-active": (0, "active\n")})

    assert service_systemd.status() == "OpenGeneral daemon: running"


def test_status_normalizes_inactive_to_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    _scripted_systemctl(monkeypatch, {"is-active": (0, "inactive\n")})

    assert service_systemd.status() == "OpenGeneral daemon: stopped"


def test_status_normalizes_reloading_to_running(monkeypatch: pytest.MonkeyPatch) -> None:
    _scripted_systemctl(monkeypatch, {"is-active": (0, "reloading\n")})

    assert service_systemd.status() == "OpenGeneral daemon: running"


def test_uninstall_warns_on_real_disable_failure(
    isolated_unit_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolated_unit_dir.mkdir(parents=True, exist_ok=True)
    unit_path = isolated_unit_dir / service_systemd.SERVICE_NAME
    unit_path.write_text("stub", encoding="utf-8")
    _scripted_systemctl(monkeypatch, {"disable": (1, "Failed to disable: permission denied")})

    result = service_systemd.uninstall()

    assert not unit_path.exists()
    assert "Warning" in result
    assert "permission denied" in result


def test_uninstall_quiet_when_unit_not_loaded(
    isolated_unit_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolated_unit_dir.mkdir(parents=True, exist_ok=True)
    unit_path = isolated_unit_dir / service_systemd.SERVICE_NAME
    unit_path.write_text("stub", encoding="utf-8")
    # Exit code 5 == unit not loaded; an acceptable state for uninstall.
    _scripted_systemctl(monkeypatch, {"disable": (5, "Unit not loaded.")})

    result = service_systemd.uninstall()

    assert "Warning" not in result


def test_systemctl_missing_raises_with_foreground_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: None)

    with pytest.raises(RuntimeError, match="foreground"):
        service_systemd.start()
