"""Run the platform installer script (install.sh / install.ps1) as a pytest scenario.

This folds the offline installer checks into pytest so they appear in the Allure
report alongside the unit and integration scenarios. The underlying scripts set up
a fake release, stub the downloader, and assert install + checksum-verify +
uninstall; their full output is captured here.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_installer_script(binary: str) -> None:
    if sys.platform == "win32":
        cmd = ["pwsh", "-File", str(ROOT / "tests" / "installer" / "run_install.ps1")]
    else:
        cmd = ["bash", str(ROOT / "tests" / "installer" / "run_install_sh.sh")]

    # The shared `binary` fixture resolves $OPENGENERAL_BINARY or the default build
    # output; pass it through so the script installs the real product binary.
    env = {**os.environ, "OPENGENERAL_BINARY": binary}
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    assert result.returncode == 0, (
        f"installer script failed (exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
    )
