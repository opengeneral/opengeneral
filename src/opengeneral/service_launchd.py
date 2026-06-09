from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

from opengeneral.service import daemon_args, daemon_command

LABEL = "com.opengeneral.daemon"
_PID_PATTERN = re.compile(r'"PID"\s*=\s*\d+')


def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _domain_target() -> str:
    return f"gui/{os.getuid()}"


def _service_target() -> str:
    return f"gui/{os.getuid()}/{LABEL}"


def plist_content() -> str:
    program_args = "".join(
        f"        <string>{escape(arg)}</string>\n" for arg in daemon_args()
    )
    # KeepAlive Crashed-only means launchd restarts the daemon if it is killed by a
    # signal, but NOT when it exits cleanly. A clean exit covers both a graceful
    # stop (code 0) and the config-error exit (code 78), so a bad config does not
    # produce a restart loop — the launchd analogue of systemd RestartPreventExitStatus.
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
    result = subprocess.run(
        ["launchctl", *args],
        capture_output=True,
        text=True,
        check=False,
    )
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


def install() -> str:
    path = plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    path.write_text(plist_content(), encoding="utf-8")
    # Bootout any prior registration so a reinstall picks up the new plist cleanly.
    _launchctl("bootout", _service_target(), check=False)
    try:
        _launchctl("bootstrap", _domain_target(), str(path))
    except Exception:
        if previous is not None:
            path.write_text(previous, encoding="utf-8")
            _launchctl("bootstrap", _domain_target(), str(path), check=False)
        else:
            path.unlink(missing_ok=True)
        raise
    return (
        f"Installed launchd user agent at {path}.\n"
        f"The agent runs: {daemon_command()}\n"
        "Re-run `opengeneral daemon install` if that path changes "
        "(e.g. you rebuild the environment or move the binary)."
    )


def uninstall() -> str:
    path = plist_path()
    _launchctl("bootout", _service_target(), check=False)
    if path.exists():
        path.unlink()
    return f"Uninstalled launchd user agent at {path}"


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
