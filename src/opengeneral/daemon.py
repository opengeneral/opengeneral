from __future__ import annotations

import asyncio
import json
import socketserver
from dataclasses import dataclass
from typing import Any

from opengeneral.action_plane import ActionPlaneConnector, EmptyActionPlaneConnector
from opengeneral.agent import GeneralPurposeAgent
from opengeneral.config import (
    DEFAULT_ACTION_PLANES_CONFIG_PATH,
    DEFAULT_AGENTS_CONFIG_PATH,
    ActionPlaneConfig,
    ActionPlanesConfig,
    AgentConfig,
    AgentsConfig,
)
from opengeneral.daemon_client import DEFAULT_DAEMON_HOST, DEFAULT_DAEMON_PORT
from opengeneral.personas import AgentPersona, PersonaRegistry
from opengeneral.runtime import AgentRuntime


@dataclass
class RunningAgent:
    config: AgentConfig
    action_plane: ActionPlaneConfig
    persona: AgentPersona
    runtime: AgentRuntime
    agent: GeneralPurposeAgent
    status: str = "idle"
    last_error: str | None = None


class AgentManager:
    def __init__(self, connector: ActionPlaneConnector | None = None) -> None:
        self.connector = connector or EmptyActionPlaneConnector()
        self.agents: dict[str, RunningAgent] = {}

    async def load_existing(self) -> None:
        agents_config = AgentsConfig.from_path(DEFAULT_AGENTS_CONFIG_PATH)
        for config in agents_config.agents.values():
            await self._start(config)

    async def spawn(self, config: AgentConfig) -> dict[str, str | None]:
        agents_config = AgentsConfig.from_path(DEFAULT_AGENTS_CONFIG_PATH)
        if config.name in agents_config.agents or config.name in self.agents:
            raise ValueError(f"Agent already exists: {config.name}")
        await self._start(config)
        agents = dict(agents_config.agents)
        agents[config.name] = config
        AgentsConfig(agents=agents).write(DEFAULT_AGENTS_CONFIG_PATH)
        return self.get_agent(config.name)

    async def _start(self, config: AgentConfig) -> RunningAgent:
        action_planes_config = ActionPlanesConfig.from_path(DEFAULT_ACTION_PLANES_CONFIG_PATH)
        action_plane = action_planes_config.action_planes.get(config.action_plane)
        if action_plane is None:
            raise ValueError(f"Action plane not found: {config.action_plane}")

        persona = PersonaRegistry().load(config.persona_tag)
        clients = await self.connector.connect(action_plane.endpoint, config.agent_id)
        runtime = AgentRuntime(
            manifest=persona.manifest,
            clients=clients,
            action_plane=action_plane.name,
            identity=config.agent_id,
        )
        running = RunningAgent(
            config=config,
            action_plane=action_plane,
            persona=persona,
            runtime=runtime,
            agent=GeneralPurposeAgent(runtime),
        )
        self.agents[config.name] = running
        return running

    async def send_message(self, name: str, content: str) -> dict[str, list[str]]:
        running = self.agents.get(name)
        if running is None:
            raise ValueError(f"Agent not found: {name}")
        try:
            running.status = "processing"
            return {"messages": [await running.agent.respond(content)]}
        except Exception as error:
            running.status = "error"
            running.last_error = str(error)
            raise
        finally:
            if running.status != "error":
                running.status = "idle"

    def list_agents(self) -> list[dict[str, str | None]]:
        return [self.get_agent(name) for name in sorted(self.agents)]

    def get_agent(self, name: str) -> dict[str, str | None]:
        running = self.agents.get(name)
        if running is None:
            raise ValueError(f"Agent not found: {name}")
        return {
            "name": running.config.name,
            "id": running.config.agent_id,
            "persona": running.config.persona_tag,
            "action_plane": running.config.action_plane,
            "status": running.status,
            "last_error": running.last_error,
        }

    def remove_agent(self, name: str) -> dict[str, str]:
        if name not in self.agents:
            raise ValueError(f"Agent not found: {name}")
        running = self.agents.pop(name)
        agents_config = AgentsConfig.from_path(DEFAULT_AGENTS_CONFIG_PATH)
        agents = dict(agents_config.agents)
        agents.pop(name, None)
        AgentsConfig(agents=agents).write(DEFAULT_AGENTS_CONFIG_PATH)
        return {"name": running.config.name, "id": running.config.agent_id}

    def status(self) -> dict[str, Any]:
        return {"status": "running", "agents": len(self.agents)}


class DaemonRequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        line = self.rfile.readline()
        if not line:
            return
        request = json.loads(line.decode("utf-8"))
        response = self.server.handle_request_payload(request)  # type: ignore[attr-defined]
        self.wfile.write(json.dumps(response).encode("utf-8") + b"\n")
        self.wfile.flush()


class OpenGeneralDaemon(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, host: str, port: int, manager: AgentManager) -> None:
        self.manager = manager
        self.should_stop = False
        super().__init__((host, port), DaemonRequestHandler)

    def handle_request_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("id")
        try:
            result = self._dispatch(request.get("method"), request.get("params") or {})
            return {"id": request_id, "ok": True, "result": result}
        except Exception as error:
            return {"id": request_id, "ok": False, "error": str(error)}

    def _dispatch(self, method: str, params: dict[str, Any]) -> Any:
        if method == "daemon.status":
            return self.manager.status()
        if method == "daemon.stop":
            self.should_stop = True
            return {"status": "stopping"}
        if method == "agent.spawn":
            return asyncio.run(
                self.manager.spawn(
                    AgentConfig(
                        name=params["name"],
                        agent_id=params["id"],
                        persona_tag=params["persona"],
                        action_plane=params["action_plane"],
                    )
                )
            )
        if method == "agent.list":
            return self.manager.list_agents()
        if method == "agent.show":
            return self.manager.get_agent(params["name"])
        if method == "agent.remove":
            return self.manager.remove_agent(params["name"])
        if method == "agent.message":
            return asyncio.run(self.manager.send_message(params["name"], params["content"]))
        raise ValueError(f"Unknown daemon method: {method}")

    def serve_until_stopped(self) -> None:
        while not self.should_stop:
            self.handle_request()
        self.server_close()


def serve(host: str = DEFAULT_DAEMON_HOST, port: int = DEFAULT_DAEMON_PORT) -> None:
    manager = AgentManager()
    asyncio.run(manager.load_existing())
    daemon = OpenGeneralDaemon(host, port, manager)
    daemon.serve_until_stopped()


if __name__ == "__main__":
    serve()
