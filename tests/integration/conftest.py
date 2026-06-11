"""Integration fixtures that drive the built `opengeneral` binary as a black box.

The binary is resolved by the shared `binary` fixture (tests/conftest.py): it uses
$OPENGENERAL_BINARY, else the default build output dist/opengeneral[.exe], and skips
when neither exists. So `./packaging/build.sh && pytest` runs these automatically.
Each test gets an isolated OPENGENERAL_HOME and a free daemon port, and the binary
runs with cwd set to a scratch dir — important, because the default personas/skills
are loaded via a relative `Path("personas")`, so running from the repo root would
mask the (intentional, documented) bundling gap.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _rpc(host: str, port: int, method: str, params: dict | None = None, timeout: float = 3.0) -> dict:
    request = {"id": "test", "method": method, "params": params or {}}
    with socket.create_connection((host, port), timeout=timeout) as client:
        client.sendall(json.dumps(request).encode("utf-8") + b"\n")
        line = client.makefile("rb").readline()
    return json.loads(line.decode("utf-8"))


@pytest.fixture
def og_home(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    # A scratch CWD with no personas/ or skills/ subdir, reproducing a real install.
    d = tmp_path / "work"
    d.mkdir()
    return d


@pytest.fixture
def env(og_home: Path) -> dict[str, str]:
    e = dict(os.environ)
    e["OPENGENERAL_HOME"] = str(og_home)
    e["OPENGENERAL_DAEMON_HOST"] = "127.0.0.1"
    e["OPENGENERAL_DAEMON_PORT"] = str(_free_port())
    return e


@pytest.fixture
def run(binary: str, env: dict[str, str], workdir: Path) -> Callable[..., subprocess.CompletedProcess]:
    def _run(*args: str, stdin: str | None = None, timeout: int = 30) -> subprocess.CompletedProcess:
        return subprocess.run(
            [binary, *args],
            env=env,
            input=stdin,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    return _run


@dataclass
class RunningDaemon:
    proc: subprocess.Popen
    host: str
    port: int

    def rpc(self, method: str, params: dict | None = None) -> dict:
        return _rpc(self.host, self.port, method, params)

    def stop(self) -> int | None:
        try:
            self.rpc("daemon.stop")
        except OSError:
            pass
        try:
            return self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:
                return self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                return self.proc.wait(timeout=5)


@pytest.fixture
def daemon(binary: str, env: dict[str, str], workdir: Path):
    host = env["OPENGENERAL_DAEMON_HOST"]

    # Pre-picking a free port then handing it to a separate process is inherently
    # racy (another listener can grab the port between probe and bind, which is
    # more frequent on Windows). Retry on a fresh port if the daemon exits during
    # startup. The working port is written back to env so the `run` fixture agrees.
    running: RunningDaemon | None = None
    last_out = ""
    for _ in range(4):
        port = _free_port()
        env["OPENGENERAL_DAEMON_PORT"] = str(port)
        proc = subprocess.Popen(
            [binary, "daemon", "run"],
            env=env,
            cwd=str(workdir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        deadline = time.time() + 25
        ready = False
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            try:
                resp = _rpc(host, port, "daemon.status")
                if resp.get("ok") and resp["result"].get("status") == "running":
                    ready = True
                    break
            except OSError:
                pass
            time.sleep(0.3)

        if ready:
            running = RunningDaemon(proc=proc, host=host, port=port)
            break

        # Failed to come up — capture output, ensure it's dead, then retry.
        if proc.poll() is None:
            proc.terminate()
            try:
                last_out = proc.communicate(timeout=5)[0]
            except subprocess.TimeoutExpired:
                proc.kill()
                last_out = proc.communicate()[0]
        else:
            last_out = proc.communicate()[0]

    if running is None:
        pytest.fail(f"daemon did not become ready after retries:\n{last_out}")

    yield running
    if running.proc.poll() is None:
        running.stop()
