from __future__ import annotations

import json
import os
import socket
from typing import Any
from uuid import uuid4

DEFAULT_DAEMON_HOST = os.environ.get("OPENGENERAL_DAEMON_HOST", "127.0.0.1")
DEFAULT_DAEMON_PORT = int(os.environ.get("OPENGENERAL_DAEMON_PORT", "4777"))
DAEMON_NOT_RUNNING = "OpenGeneral daemon is not running. Start it with: opengeneral daemon start"


class DaemonUnavailableError(RuntimeError):
    pass


class DaemonClient:
    def __init__(
        self,
        host: str = DEFAULT_DAEMON_HOST,
        port: int = DEFAULT_DAEMON_PORT,
    ) -> None:
        self.host = host
        self.port = port

    def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        request = {"id": uuid4().hex, "method": method, "params": params or {}}
        try:
            with socket.create_connection((self.host, self.port), timeout=2) as client:
                reader = client.makefile("rwb")
                reader.write(json.dumps(request).encode("utf-8") + b"\n")
                reader.flush()
                line = reader.readline()
        except OSError as error:
            raise DaemonUnavailableError(DAEMON_NOT_RUNNING) from error

        if not line:
            raise DaemonUnavailableError("OpenGeneral daemon closed the connection without a response")

        response = json.loads(line.decode("utf-8"))
        if not response.get("ok", False):
            raise RuntimeError(response.get("error", "OpenGeneral daemon request failed"))
        return response.get("result")

    def status(self) -> Any:
        return self.request("daemon.status")

    def stop(self) -> Any:
        return self.request("daemon.stop")

    def spawn_agent(self, name: str, persona: str, action_plane: str, key: str, model: str, agent_id: str) -> Any:
        return self.request(
            "agent.spawn",
            {"name": name, "id": agent_id, "persona": persona, "action_plane": action_plane, "key": key, "model": model},
        )

    def list_agents(self) -> Any:
        return self.request("agent.list")

    def show_agent(self, name: str) -> Any:
        return self.request("agent.show", {"name": name})

    def remove_agent(self, name: str) -> Any:
        return self.request("agent.remove", {"name": name})

    def send_message(self, name: str, content: str) -> Any:
        return self.request(
            "agent.message",
            {"name": name, "content": content, "source": "chat"},
        )
