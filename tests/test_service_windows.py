from __future__ import annotations

import sys

import pytest

# conftest's collect_ignore keeps this module off non-Windows runs entirely (so it
# leaves no skipped row in the report). The skipif is only a fallback for an explicit
# single-file run on the wrong OS: the SCM backend needs pywin32, a win32-only dep.
pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="Windows SCM backend is Windows-only"
)

from opengeneral import service_windows


def _patch_serviceutil(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """Record win32serviceutil calls instead of touching the real SCM."""
    calls: list[tuple] = []

    def recorder(name: str):
        def _call(*args, **kwargs):  # noqa: ANN001, ANN202
            calls.append((name, args, kwargs))
        return _call

    for fn in ("InstallService", "RemoveService", "StartService", "StopService"):
        monkeypatch.setattr(service_windows.win32serviceutil, fn, recorder(fn))
    return calls


def _set_query_state(monkeypatch: pytest.MonkeyPatch, state: int) -> None:
    monkeypatch.setattr(
        service_windows.win32serviceutil,
        "QueryServiceStatus",
        lambda name: (0, state, 0, 0, 0, 0, 0),
    )


def test_install_registers_the_service(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_serviceutil(monkeypatch)

    result = service_windows.install()

    install_calls = [c for c in calls if c[0] == "InstallService"]
    assert len(install_calls) == 1
    args = install_calls[0][1]
    assert f"{service_windows.__name__}.OpenGeneralService" in args
    assert service_windows.SERVICE_NAME in args
    assert "Installed Windows service" in result


def test_status_state_maps_running(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_query_state(monkeypatch, service_windows.win32service.SERVICE_RUNNING)

    assert service_windows.status_state() == "running"
    assert service_windows.status() == "OpenGeneral daemon: running"


def test_status_state_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    err = service_windows.pywintypes.error(
        service_windows._SERVICE_NOT_INSTALLED, "QueryServiceStatus", "not installed"
    )

    def _raise(name):  # noqa: ANN001, ANN202
        raise err

    monkeypatch.setattr(service_windows.win32serviceutil, "QueryServiceStatus", _raise)

    assert service_windows.status_state() == "not installed"


def test_start_is_idempotent_when_running(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_serviceutil(monkeypatch)
    _set_query_state(monkeypatch, service_windows.win32service.SERVICE_RUNNING)

    result = service_windows.start()

    assert result == "OpenGeneral daemon already running"
    assert not [c for c in calls if c[0] == "StartService"]


def test_start_when_stopped_calls_startservice(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_serviceutil(monkeypatch)
    _set_query_state(monkeypatch, service_windows.win32service.SERVICE_STOPPED)

    result = service_windows.start()

    assert result == "Started OpenGeneral daemon"
    assert [c for c in calls if c[0] == "StartService"]


def test_uninstall_tolerates_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    def stop_raise(name):  # noqa: ANN001, ANN202
        raise service_windows.pywintypes.error(
            service_windows._SERVICE_NOT_ACTIVE, "StopService", "not active"
        )

    def remove_raise(name):  # noqa: ANN001, ANN202
        raise service_windows.pywintypes.error(
            service_windows._SERVICE_NOT_INSTALLED, "RemoveService", "not installed"
        )

    monkeypatch.setattr(service_windows.win32serviceutil, "StopService", stop_raise)
    monkeypatch.setattr(service_windows.win32serviceutil, "RemoveService", remove_raise)

    result = service_windows.uninstall()

    assert "was not installed" in result
