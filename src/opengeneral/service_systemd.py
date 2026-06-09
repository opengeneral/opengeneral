from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from opengeneral.daemon import CONFIG_ERROR_EXIT_CODE
from opengeneral.service import daemon_command  # re-exported for unit_content() and tests

SERVICE_NAME = "opengeneral.service"

# systemctl exit code returned when the unit is not loaded/enabled — acceptable
# during uninstall, since the goal is simply for it to be gone.
_SYSTEMCTL_NOT_LOADED = 5

_STATE_ALIASES = {
    "active": "running",
    "reloading": "running",
    "activating": "starting",
    "deactivating": "stopping",
    "inactive": "stopped",
    "failed": "failed",
}


def user_unit_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base).expanduser() / "systemd" / "user"


def unit_content() -> str:
    return (
        "[Unit]\n"
        "Description=OpenGeneral agent supervisor daemon\n"
        "After=default.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={daemon_command()}\n"
        "Restart=on-failure\n"
        "RestartSec=2\n"
        f"RestartPreventExitStatus={CONFIG_ERROR_EXIT_CODE}\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def _systemctl(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    if not shutil.which("systemctl"):
        raise RuntimeError(
            "systemctl not found. The OpenGeneral daemon needs a systemd user session "
            "(unavailable on Alpine/minimal containers and WSL1). You can still run the "
            "daemon in the foreground with: opengeneral daemon run"
        )
    result = subprocess.run(
        ["systemctl", "--user", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"systemctl --user {' '.join(args)} failed: {message}")
    return result


def status_state() -> str:
    raw = _systemctl("is-active", SERVICE_NAME, check=False).stdout.strip()
    return _STATE_ALIASES.get(raw, raw or "unknown")


def install() -> str:
    unit_dir = user_unit_dir()
    unit_dir.mkdir(parents=True, exist_ok=True)
    unit_path = unit_dir / SERVICE_NAME
    previous = unit_path.read_text(encoding="utf-8") if unit_path.exists() else None
    unit_path.write_text(unit_content(), encoding="utf-8")
    try:
        _systemctl("daemon-reload")
        _systemctl("enable", SERVICE_NAME)
    except Exception:
        if previous is not None:
            unit_path.write_text(previous, encoding="utf-8")
        else:
            unit_path.unlink(missing_ok=True)
        _systemctl("daemon-reload", check=False)
        raise
    return (
        f"Installed systemd user service at {unit_path}.\n"
        f"The unit runs: {daemon_command()}\n"
        "Re-run `opengeneral daemon install` if that path changes "
        "(e.g. you rebuild the environment or move the binary).\n"
        "If you want the daemon to keep running after you log out, "
        "enable lingering once: loginctl enable-linger $USER"
    )


def uninstall() -> str:
    unit_path = user_unit_dir() / SERVICE_NAME
    disable = _systemctl("disable", "--now", SERVICE_NAME, check=False)
    if unit_path.exists():
        unit_path.unlink()
    _systemctl("daemon-reload", check=False)
    message = f"Uninstalled systemd user service at {unit_path}"
    if disable.returncode not in (0, _SYSTEMCTL_NOT_LOADED):
        warning = (disable.stderr or disable.stdout or "").strip()
        message += (
            f"\nWarning: `systemctl --user disable --now {SERVICE_NAME}` reported: {warning}\n"
            "The unit file was removed, but systemd may still hold a stale enable link; "
            "run `systemctl --user daemon-reload` once the user session is reachable."
        )
    return message


def start() -> str:
    if status_state() == "running":
        return "OpenGeneral daemon already running"
    _systemctl("start", SERVICE_NAME)
    return "Started OpenGeneral daemon"


def stop() -> str:
    if status_state() == "stopped":
        return "OpenGeneral daemon already stopped"
    _systemctl("stop", SERVICE_NAME)
    return "Stopped OpenGeneral daemon"


def status() -> str:
    return f"OpenGeneral daemon: {status_state()}"
