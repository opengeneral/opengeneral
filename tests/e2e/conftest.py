"""End-to-end service-journey fixtures — the *default* end-user path.

These install the binary's OS service (systemd / launchd / SCM — abstracted by the
binary itself, so no per-OS code here), start it, and drive the CLI against the
service-managed daemon on the default 127.0.0.1:4777.

Gated behind OPENGENERAL_E2E=1: the `service` fixture installs and starts a REAL OS
service and touches the default OPENGENERAL_HOME (~/.opengeneral). CI's e2e job sets
the flag; a plain local `pytest` skips these so it never registers a service on a
developer's machine. The binary path comes from the shared `binary` fixture
(tests/conftest.py) — in CI that's the installer-placed binary on PATH.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from dataclasses import dataclass

import pytest

# The OS service launches `<binary> daemon run` with no captured env, so a
# service-managed daemon always binds the defaults — never an isolated test port.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4777


def _rpc(method: str, timeout: float = 3.0) -> dict:
    request = {"id": "e2e", "method": method, "params": {}}
    with socket.create_connection((DEFAULT_HOST, DEFAULT_PORT), timeout=timeout) as client:
        client.sendall(json.dumps(request).encode("utf-8") + b"\n")
        line = client.makefile("rb").readline()
    return json.loads(line.decode("utf-8"))


@dataclass
class Service:
    binary: str
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT

    def rpc(self, method: str) -> dict:
        return _rpc(method)

    def cli(self, *args: str, stdin: str | None = None, timeout: int = 30) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.binary, *args], input=stdin, capture_output=True, text=True, timeout=timeout
        )


@pytest.fixture(scope="session")
def service(binary: str):
    if os.environ.get("OPENGENERAL_E2E") != "1":
        pytest.skip(
            "set OPENGENERAL_E2E=1 to run the service-journey e2e tests "
            "(they install and start a real OS service)"
        )

    def _cleanup() -> None:
        subprocess.run([binary, "daemon", "stop"], capture_output=True, text=True, timeout=60)
        subprocess.run([binary, "daemon", "uninstall"], capture_output=True, text=True, timeout=60)

    try:
        installed = subprocess.run(
            [binary, "daemon", "install"], capture_output=True, text=True, timeout=60
        )
        assert installed.returncode == 0, f"daemon install failed:\n{installed.stdout}\n{installed.stderr}"
        started = subprocess.run(
            [binary, "daemon", "start"], capture_output=True, text=True, timeout=60
        )
        assert started.returncode == 0, f"daemon start failed:\n{started.stdout}\n{started.stderr}"

        deadline = time.time() + 30
        ready = False
        while time.time() < deadline:
            try:
                resp = _rpc("daemon.status")
                if resp.get("ok") and resp["result"].get("status") == "running":
                    ready = True
                    break
            except OSError:
                pass
            time.sleep(0.4)
        assert ready, "service-managed daemon did not start serving RPC on 127.0.0.1:4777"
    except Exception:
        _cleanup()
        raise

    yield Service(binary=binary)
    _cleanup()
