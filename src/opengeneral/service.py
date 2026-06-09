from __future__ import annotations

import platform
import sys
from types import ModuleType


def daemon_args() -> list[str]:
    """Argv that launches the daemon in the foreground.

    A frozen binary (PyInstaller/Nuitka) has no ``-m`` form, so it gets its own
    ``daemon run`` subcommand; the source checkout runs the module directly.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "daemon", "run"]
    return [sys.executable, "-m", "opengeneral.daemon"]


def daemon_command() -> str:
    return " ".join(daemon_args())


def _backend() -> ModuleType:
    system = platform.system()
    if system == "Linux":
        from opengeneral import service_systemd

        return service_systemd
    if system == "Darwin":
        from opengeneral import service_launchd

        return service_launchd
    if system == "Windows":
        from opengeneral import service_windows

        return service_windows
    raise RuntimeError(
        f"Unsupported platform for the OpenGeneral daemon service: {system}. "
        "Run the daemon in the foreground instead: opengeneral daemon run"
    )


def install() -> str:
    return _backend().install()


def uninstall() -> str:
    return _backend().uninstall()


def start() -> str:
    return _backend().start()


def stop() -> str:
    return _backend().stop()


def status() -> str:
    return _backend().status()
