"""Tiny Windows SCM service host for the OpenGeneral daemon.

PyInstaller builds this into `opengeneral-svc.exe`, a deliberately minimal binary:
it imports only pywin32 + the stdlib, so it extracts and starts within the SCM start
timeout even as a one-file build (the heavy `opengeneral.exe` does not). Its only job
is to host the SCM dispatcher and supervise the real daemon as a child process —
`opengeneral.exe daemon run`, the sibling binary shipped alongside this host.

On stop it asks the daemon to shut down cleanly over the localhost RPC, then
terminates the child if it does not exit in time.

The service identity strings below MUST match opengeneral.service_windows, which
registers the service (pointing its ImagePath at this host exe).
"""

from __future__ import annotations

import json
import multiprocessing
import os
import socket
import subprocess
import sys
from pathlib import Path

import servicemanager
import win32event
import win32service
import win32serviceutil

SERVICE_NAME = "OpenGeneralDaemon"
SERVICE_DISPLAY = "OpenGeneral Daemon"
SERVICE_DESCRIPTION = "OpenGeneral agent supervisor daemon."

_HOST = os.environ.get("OPENGENERAL_DAEMON_HOST", "127.0.0.1")
_PORT = int(os.environ.get("OPENGENERAL_DAEMON_PORT", "4777"))


def _log(message: str, error: bool = False) -> None:
    # Event-log writes need servicemanager's message resource, which may be absent in
    # a frozen build; never let logging take the service down.
    try:
        (servicemanager.LogErrorMsg if error else servicemanager.LogInfoMsg)(message)
    except Exception:
        pass


def _main_binary() -> Path:
    # opengeneral.exe ships next to this host (opengeneral-svc.exe).
    return Path(sys.executable).with_name("opengeneral.exe")


def _machine_home() -> str:
    # Machine-wide config/state dir (must match service_windows.machine_home()).
    base = os.environ.get("ProgramData", r"C:\ProgramData")
    return str(Path(base) / "OpenGeneral")


def _request_daemon_stop() -> None:
    request = json.dumps({"id": "svc-stop", "method": "daemon.stop", "params": {}}).encode("utf-8")
    try:
        with socket.create_connection((_HOST, _PORT), timeout=2) as client:
            client.sendall(request + b"\n")
            client.makefile("rb").readline()
    except OSError:
        pass


class OpenGeneralServiceHost(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY
    _svc_description_ = SERVICE_DESCRIPTION

    def __init__(self, args: object) -> None:
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.child: subprocess.Popen | None = None

    def SvcStop(self) -> None:
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        _request_daemon_stop()
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self) -> None:
        # Generous wait hint: the child is the full one-file binary and may take a few
        # seconds to extract before it binds — but we report RUNNING as soon as it spawns.
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING, waitHint=60000)
        main = _main_binary()
        if not main.exists():
            _log(f"OpenGeneral host: daemon binary not found at {main}", error=True)
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
            return
        try:
            env = {**os.environ, "OPENGENERAL_HOME": _machine_home()}
            self.child = subprocess.Popen([str(main), "daemon", "run"], env=env)
        except OSError as error:
            _log(f"OpenGeneral host: failed to start daemon: {error}", error=True)
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
            return

        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        _log(f"OpenGeneral daemon started (pid {self.child.pid}).")

        # Run until the SCM asks us to stop, or the child exits on its own.
        while True:
            if win32event.WaitForSingleObject(self.stop_event, 1000) == win32event.WAIT_OBJECT_0:
                break
            if self.child.poll() is not None:
                break

        if self.child.poll() is None:
            _request_daemon_stop()
            try:
                self.child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.child.terminate()
                try:
                    self.child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.child.kill()
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)


def run_host() -> None:
    servicemanager.Initialize()
    servicemanager.PrepareToHostSingle(OpenGeneralServiceHost)
    servicemanager.StartServiceCtrlDispatcher()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    run_host()
