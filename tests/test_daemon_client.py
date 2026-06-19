from __future__ import annotations

import json
import socket
import threading
import time

import pytest

from opengeneral.daemon_client import DaemonClient, DaemonUnavailableError


def test_daemon_client_reports_unavailable_daemon() -> None:
    client = DaemonClient("127.0.0.1", 9)

    with pytest.raises(DaemonUnavailableError):
        client.status()


class _SlowDaemon:
    """A daemon that accepts, then waits `delay` seconds before replying."""

    def __init__(self, delay: float) -> None:
        self.delay = delay
        self._sock = socket.socket()
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(1)
        self.port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            with conn:
                stream = conn.makefile("rwb")
                line = stream.readline()
                if not line:
                    continue
                request_id = json.loads(line.decode())["id"]
                time.sleep(self.delay)
                stream.write(
                    json.dumps(
                        {"id": request_id, "ok": True, "result": {"status": "running"}}
                    ).encode()
                    + b"\n"
                )
                stream.flush()

    def close(self) -> None:
        self._sock.close()


def test_short_read_timeout_treats_a_slow_daemon_as_unavailable() -> None:
    server = _SlowDaemon(delay=0.5)
    client = DaemonClient("127.0.0.1", server.port)
    try:
        with pytest.raises(DaemonUnavailableError):
            client.request("daemon.status", read_timeout=0.1)
    finally:
        server.close()


def test_long_read_timeout_lets_a_slow_daemon_answer() -> None:
    server = _SlowDaemon(delay=0.5)
    client = DaemonClient("127.0.0.1", server.port)
    try:
        assert client.request("daemon.status", read_timeout=5.0)["status"] == "running"
    finally:
        server.close()


def test_send_message_uses_a_generous_read_timeout(monkeypatch) -> None:
    captured: dict = {}

    def fake_request(self, method, params=None, read_timeout=15.0):
        captured["method"] = method
        captured["read_timeout"] = read_timeout
        return {"messages": []}

    monkeypatch.setattr(DaemonClient, "request", fake_request)

    DaemonClient().send_message("agent", "hi")

    # An agent turn runs the model + tools, so it must not use the short default.
    assert captured["method"] == "agent.message"
    assert captured["read_timeout"] >= 60
