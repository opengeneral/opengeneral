from __future__ import annotations

import asyncio
import functools
import sys
import threading
import traceback
from typing import Callable, TypeVar

from opengeneral.daemon_client import DEFAULT_DAEMON_HOST, DEFAULT_DAEMON_PORT

SERVICE_NAME = "OpenGeneralDaemon"
SERVICE_DISPLAY = "OpenGeneral Daemon"
SERVICE_DESCRIPTION = "OpenGeneral agent supervisor daemon."

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

            try:
                self.daemon.serve_forever()
            finally:
                self.daemon.server_close()


@_require_pywin32
def install() -> str:
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
