from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from opengeneral.daemon import CONFIG_ERROR_EXIT_CODE
from opengeneral.service import daemon_command  # re-exported for unit_content() and tests

SERVICE_NAME = "opengeneral.service"

# A system-wide unit so the daemon runs at boot, independent of any login, under a
# least-privilege account: systemd's DynamicUser allocates an ephemeral system user
# and a state directory (/var/lib/opengeneral) it owns — no login, no home, no manual
# account to create. Installing/managing it requires root (run with sudo).
SYSTEM_UNIT_DIR = Path("/etc/systemd/system")
STATE_DIRECTORY_NAME = "opengeneral"
MACHINE_HOME = f"/var/lib/{STATE_DIRECTORY_NAME}"

# systemctl exit code returned when the unit is not loaded — acceptable during
# uninstall, where the goal is simply for it to be gone.
_SYSTEMCTL_NOT_LOADED = 5

_STATE_ALIASES = {
    "active": "running",
    "reloading": "running",
    "activating": "starting",
    "deactivating": "stopping",
    "inactive": "stopped",
    "failed": "failed",
}


def unit_content() -> str:
    return (
        "[Unit]\n"
        "Description=OpenGeneral agent supervisor daemon\n"
        "After=network.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={daemon_command()}\n"
        "DynamicUser=yes\n"
        f"StateDirectory={STATE_DIRECTORY_NAME}\n"
        f"Environment=OPENGENERAL_HOME={MACHINE_HOME}\n"
        "Restart=on-failure\n"
        "RestartSec=2\n"
        f"RestartPreventExitStatus={CONFIG_ERROR_EXIT_CODE}\n"
        "\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )


def _systemctl(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    if not shutil.which("systemctl"):
        raise RuntimeError(
            "systemctl not found. The OpenGeneral daemon needs systemd (unavailable on "
            "Alpine/minimal containers and WSL1). You can still run the daemon in the "
            "foreground with: opengeneral daemon run"
        )
    result = subprocess.run(["systemctl", *args], capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"systemctl {' '.join(args)} failed: {message}")
    return result


def status_state() -> str:
    raw = _systemctl("is-active", SERVICE_NAME, check=False).stdout.strip()
    return _STATE_ALIASES.get(raw, raw or "unknown")


def install() -> str:
    unit_path = SYSTEM_UNIT_DIR / SERVICE_NAME
    SYSTEM_UNIT_DIR.mkdir(parents=True, exist_ok=True)
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
        f"Installed systemd service at {unit_path}.\n"
        f"It runs as a DynamicUser with state in {MACHINE_HOME}; launch command: {daemon_command()}.\n"
        "Re-run `sudo opengeneral daemon install` if the binary path changes.\n"
        "Start it with: sudo opengeneral daemon start"
    )


def uninstall() -> str:
    unit_path = SYSTEM_UNIT_DIR / SERVICE_NAME
    disable = _systemctl("disable", "--now", SERVICE_NAME, check=False)
    if unit_path.exists():
        unit_path.unlink()
    _systemctl("daemon-reload", check=False)
    message = f"Uninstalled systemd service at {unit_path}"
    if disable.returncode not in (0, _SYSTEMCTL_NOT_LOADED):
        warning = (disable.stderr or disable.stdout or "").strip()
        message += f"\nWarning: `systemctl disable --now {SERVICE_NAME}` reported: {warning}"
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
