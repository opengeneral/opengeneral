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

import pytest

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    "OPENGENERAL_BINARY" not in os.environ,
    reason="set OPENGENERAL_BINARY to the built binary to run installer tests",
)


def test_installer_script() -> None:
    if sys.platform == "win32":
        cmd = ["pwsh", "-File", str(ROOT / "tests" / "installer" / "run_install.ps1")]
    else:
        cmd = ["bash", str(ROOT / "tests" / "installer" / "run_install_sh.sh")]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    assert result.returncode == 0, (
        f"installer script failed (exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
    )
