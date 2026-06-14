from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

from opengeneral.service import daemon_args, daemon_command

LABEL = "com.opengeneral.daemon"

# A system-wide LaunchDaemon (not a per-user LaunchAgent), so the daemon runs at boot
# under a least-privilege account independent of any login. Managed with sudo.
DAEMON_PLIST_DIR = Path("/Library/LaunchDaemons")
SERVICE_USER = "nobody"
MACHINE_HOME = Path("/Library/Application Support/OpenGeneral")

_PID_PATTERN = re.compile(r'"PID"\s*=\s*\d+')


def plist_path() -> Path:
    return DAEMON_PLIST_DIR / f"{LABEL}.plist"


def _service_target() -> str:
    return f"system/{LABEL}"


def plist_content() -> str:
    program_args = "".join(f"        <string>{escape(arg)}</string>\n" for arg in daemon_args())
    # KeepAlive Crashed-only: launchd restarts the daemon if it is killed by a signal,
    # but not on a clean exit — so a graceful stop (0) or the config-error exit (78)
    # does not loop. The launchd analogue of systemd RestartPreventExitStatus.
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        "    <key>Label</key>\n"
        f"    <string>{LABEL}</string>\n"
        "    <key>ProgramArguments</key>\n"
        "    <array>\n"
        f"{program_args}"
        "    </array>\n"
        "    <key>UserName</key>\n"
        f"    <string>{SERVICE_USER}</string>\n"
        "    <key>EnvironmentVariables</key>\n"
        "    <dict>\n"
        "        <key>OPENGENERAL_HOME</key>\n"
        f"        <string>{escape(str(MACHINE_HOME))}</string>\n"
        "    </dict>\n"
        "    <key>RunAtLoad</key>\n"
        "    <true/>\n"
        "    <key>KeepAlive</key>\n"
        "    <dict>\n"
        "        <key>Crashed</key>\n"
        "        <true/>\n"
        "    </dict>\n"
        "</dict>\n"
        "</plist>\n"
    )


def _launchctl(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    if not shutil.which("launchctl"):
        raise RuntimeError(
            "launchctl not found. macOS needs launchd to manage the OpenGeneral daemon "
            "as a service. You can still run the daemon in the foreground with: "
            "opengeneral daemon run"
        )
    result = subprocess.run(["launchctl", *args], capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"launchctl {' '.join(args)} failed: {message}")
    return result


def status_state() -> str:
    result = _launchctl("list", LABEL, check=False)
    if result.returncode != 0:
        return "not installed"
    if _PID_PATTERN.search(result.stdout):
        return "running"
    return "stopped"


def _prepare_state_dir() -> None:
    # State dir owned by the service account so the daemon can write it and other
    # users can't. Real installs run as root (sudo); a non-root call (tests) just
    # creates the dir and skips the chown.
    MACHINE_HOME.mkdir(parents=True, exist_ok=True)
    try:
        import pwd

        os.chown(MACHINE_HOME, pwd.getpwnam(SERVICE_USER).pw_uid, -1)
        os.chmod(MACHINE_HOME, 0o700)
    except (KeyError, PermissionError, OSError):
        pass


def install() -> str:
    _prepare_state_dir()
    path = plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    path.write_text(plist_content(), encoding="utf-8")
    # Bootout any prior registration so a reinstall picks up the new plist cleanly.
    _launchctl("bootout", _service_target(), check=False)
    try:
        _launchctl("bootstrap", "system", str(path))
    except Exception:
        if previous is not None:
            path.write_text(previous, encoding="utf-8")
            _launchctl("bootstrap", "system", str(path), check=False)
        else:
            path.unlink(missing_ok=True)
        raise
    return (
        f"Installed launchd system daemon at {path}.\n"
        f"It runs as {SERVICE_USER} with state in {MACHINE_HOME}; launch: {daemon_command()}.\n"
        "Re-run `sudo opengeneral daemon install` if the binary path changes."
    )


def uninstall() -> str:
    path = plist_path()
    _launchctl("bootout", _service_target(), check=False)
    if path.exists():
        path.unlink()
    return f"Uninstalled launchd system daemon at {path}"


def start() -> str:
    if status_state() == "running":
        return "OpenGeneral daemon already running"
    _launchctl("kickstart", _service_target())
    return "Started OpenGeneral daemon"


def stop() -> str:
    if status_state() in ("stopped", "not installed"):
        return "OpenGeneral daemon already stopped"
    _launchctl("kill", "TERM", _service_target())
    return "Stopped OpenGeneral daemon"


def status() -> str:
    return f"OpenGeneral daemon: {status_state()}"
