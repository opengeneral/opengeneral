from __future__ import annotations

import asyncio
import functools
import os
import subprocess
import sys
import threading
import traceback
from pathlib import Path
from typing import Callable, TypeVar

from opengeneral.daemon_client import DEFAULT_DAEMON_HOST, DEFAULT_DAEMON_PORT

SERVICE_NAME = "OpenGeneralDaemon"
SERVICE_DISPLAY = "OpenGeneral Daemon"
SERVICE_DESCRIPTION = "OpenGeneral agent supervisor daemon."

# Low-privilege virtual service account (auto-managed by the SCM, no password). The
# daemon runs as this instead of LocalSystem, so a compromise can't take the machine.
VIRTUAL_ACCOUNT = f"NT SERVICE\\{SERVICE_NAME}"


def machine_home() -> Path:
    """Machine-wide config/state dir for the Windows service (the daemon's home)."""
    base = os.environ.get("ProgramData", r"C:\ProgramData")
    return Path(base) / "OpenGeneral"

# The frozen build ships a tiny dedicated SCM host next to the main binary (see
# packaging/service_host.py). A one-file opengeneral.exe is too slow to extract to
# host the dispatcher within the SCM start timeout, so the service's ImagePath points
# at this host instead, which then supervises `opengeneral.exe daemon run`.
SERVICE_HOST_EXE = "opengeneral-svc.exe"

_SERVICE_NOT_INSTALLED = 1060
_SERVICE_NOT_ACTIVE = 1062

_STATE_LABELS_INIT = False
_STATE_LABELS: dict[int, str] = {}


def _missing() -> RuntimeError:
    return RuntimeError(
        "pywin32 is required to manage the Windows service. Install with: pip install pywin32"
    )


try:
    import pywintypes  # type: ignore[import-not-found]
    import servicemanager  # type: ignore[import-not-found]
    import win32event  # type: ignore[import-not-found]
    import win32service  # type: ignore[import-not-found]
    import win32serviceutil  # type: ignore[import-not-found]
    _HAS_PYWIN32 = True
except ImportError:
    _HAS_PYWIN32 = False


F = TypeVar("F", bound=Callable[..., object])


def _require_pywin32(func: F) -> F:
    @functools.wraps(func)
    def wrapper(*args: object, **kwargs: object) -> object:
        if not _HAS_PYWIN32:
            raise _missing()
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def _state_labels() -> dict[int, str]:
    global _STATE_LABELS_INIT, _STATE_LABELS
    if not _STATE_LABELS_INIT:
        _STATE_LABELS = {
            win32service.SERVICE_STOPPED: "stopped",
            win32service.SERVICE_START_PENDING: "starting",
            win32service.SERVICE_STOP_PENDING: "stopping",
            win32service.SERVICE_RUNNING: "running",
            win32service.SERVICE_PAUSED: "paused",
        }
        _STATE_LABELS_INIT = True
    return _STATE_LABELS


if _HAS_PYWIN32:

    class OpenGeneralService(win32serviceutil.ServiceFramework):
        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = SERVICE_DISPLAY
        _svc_description_ = SERVICE_DESCRIPTION

        def __init__(self, args: object) -> None:
            super().__init__(args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.daemon = None
            self._lifecycle_lock = threading.Lock()
            self._stop_requested = False

        def SvcStop(self) -> None:
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            with self._lifecycle_lock:
                self._stop_requested = True
                daemon = self.daemon
            if daemon is not None:
                daemon.request_shutdown()
            win32event.SetEvent(self.stop_event)

        def SvcDoRun(self) -> None:
            from opengeneral.daemon import AgentManager, OpenGeneralDaemon

            try:
                manager = AgentManager()
                asyncio.run(manager.load_existing())
            except Exception:
                servicemanager.LogErrorMsg(
                    "OpenGeneral daemon failed to load existing agents:\n"
                    + traceback.format_exc()
                )
                self.ReportServiceStatus(win32service.SERVICE_STOPPED)
                return

            with self._lifecycle_lock:
                if self._stop_requested:
                    self.ReportServiceStatus(win32service.SERVICE_STOPPED)
                    return
                self.daemon = OpenGeneralDaemon(
                    DEFAULT_DAEMON_HOST, DEFAULT_DAEMON_PORT, manager
                )

            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            try:
                self.daemon.serve_forever()
            finally:
                self.daemon.server_close()


@_require_pywin32
def install() -> str:
    if getattr(sys, "frozen", False):
        host = Path(sys.executable).with_name(SERVICE_HOST_EXE)
        if not host.exists():
            raise RuntimeError(
                f"Service host binary missing at {host}. Reinstall OpenGeneral so "
                f"{SERVICE_HOST_EXE} ships next to {Path(sys.executable).name}."
            )
        home = machine_home()
        home.mkdir(parents=True, exist_ok=True)
        win32serviceutil.InstallService(
            f"{__name__}.OpenGeneralService",  # stored but unused; the host exe hosts itself
            SERVICE_NAME,
            SERVICE_DISPLAY,
            description=SERVICE_DESCRIPTION,
            startType=win32service.SERVICE_AUTO_START,
            exeName=str(host),
            userName=VIRTUAL_ACCOUNT,
            password=None,
        )
        # Registering the service realizes the virtual account (its SID resolves only
        # after that), so grant it control of its config/state dir afterward — the
        # low-priv daemon reads/writes there, and other users can't.
        subprocess.run(
            ["icacls", str(home), "/grant", f"{VIRTUAL_ACCOUNT}:(OI)(CI)F"],
            check=True,
            capture_output=True,
            text=True,
        )
        return (
            f"Installed Windows service {SERVICE_NAME} as {VIRTUAL_ACCOUNT} "
            f"(host: {host}, state: {home})"
        )

    # Source / dev: pywin32's PythonService.exe can host the in-process class directly.
    win32serviceutil.InstallService(
        f"{__name__}.OpenGeneralService",
        SERVICE_NAME,
        SERVICE_DISPLAY,
        description=SERVICE_DESCRIPTION,
        startType=win32service.SERVICE_AUTO_START,
    )
    return f"Installed Windows service {SERVICE_NAME}"


@_require_pywin32
def uninstall() -> str:
    try:
        win32serviceutil.StopService(SERVICE_NAME)
    except pywintypes.error as error:
        if error.winerror not in (_SERVICE_NOT_INSTALLED, _SERVICE_NOT_ACTIVE):
            raise
    try:
        win32serviceutil.RemoveService(SERVICE_NAME)
    except pywintypes.error as error:
        if error.winerror == _SERVICE_NOT_INSTALLED:
            return f"Windows service {SERVICE_NAME} was not installed"
        raise
    return f"Uninstalled Windows service {SERVICE_NAME}"


@_require_pywin32
def start() -> str:
    if status_state() == "running":
        return "OpenGeneral daemon already running"
    win32serviceutil.StartService(SERVICE_NAME)
    return "Started OpenGeneral daemon"


@_require_pywin32
def stop() -> str:
    if status_state() == "stopped":
        return "OpenGeneral daemon already stopped"
    win32serviceutil.StopService(SERVICE_NAME)
    return "Stopped OpenGeneral daemon"


@_require_pywin32
def status_state() -> str:
    try:
        state = win32serviceutil.QueryServiceStatus(SERVICE_NAME)[1]
    except pywintypes.error as error:
        if error.winerror == _SERVICE_NOT_INSTALLED:
            return "not installed"
        raise
    return _state_labels().get(state, "unknown")


@_require_pywin32
def status() -> str:
    return f"OpenGeneral daemon: {status_state()}"


@_require_pywin32
def main() -> None:
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(OpenGeneralService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(OpenGeneralService)


if __name__ == "__main__":
    main()
