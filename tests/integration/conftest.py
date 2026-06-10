"""Integration fixtures that drive the built `opengeneral` binary as a black box.

Set OPENGENERAL_BINARY to the binary path (e.g. dist/opengeneral) to run these;
otherwise they skip. Each test gets an isolated OPENGENERAL_HOME and a free daemon
port, and the binary runs with cwd set to a scratch dir — important, because the
default personas/skills are loaded via a relative `Path("personas")`, so running
from the repo root would mask the (intentional, documented) bundling gap.
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


def _rpc(host: str, port: int, method: str, timeout: float = 3.0) -> dict:
    request = {"id": "test", "method": method, "params": {}}
    with socket.create_connection((host, port), timeout=timeout) as client:
        client.sendall(json.dumps(request).encode("utf-8") + b"\n")
        line = client.makefile("rb").readline()
    return json.loads(line.decode("utf-8"))


@pytest.fixture(scope="session")
def binary() -> str:
    path = os.environ.get("OPENGENERAL_BINARY")
    if not path:
        pytest.skip("set OPENGENERAL_BINARY to the built binary to run integration tests")
    if not Path(path).exists():
        pytest.skip(f"OPENGENERAL_BINARY does not exist: {path}")
    return str(Path(path).resolve())


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

    def rpc(self, method: str) -> dict:
        return _rpc(self.host, self.port, method)

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
    port = int(env["OPENGENERAL_DAEMON_PORT"])
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

    if not ready:
        proc.terminate()
        try:
            out = proc.communicate(timeout=5)[0]
        except subprocess.TimeoutExpired:
            proc.kill()
            out = ""
        pytest.fail(f"daemon did not become ready (exit={proc.poll()}):\n{out}")

    running = RunningDaemon(proc=proc, host=host, port=port)
    yield running
    if proc.poll() is None:
        running.stop()
