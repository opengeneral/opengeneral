from __future__ import annotations

import asyncio
import json
import signal
import socketserver
import sys
import threading
from dataclasses import dataclass
from typing import Any

CONFIG_ERROR_EXIT_CODE = 78

from opengeneral.action_plane import ActionPlaneConnector, MCPActionPlaneConnector
from opengeneral.agent import GeneralPurposeAgent
from opengeneral.agent_factory import create_agent
from opengeneral.config import (
    DEFAULT_ACTION_PLANES_CONFIG_PATH,
    DEFAULT_AGENTS_CONFIG_PATH,
    DEFAULT_KEYS_CONFIG_PATH,
    ActionPlaneConfig,
    ActionPlanesConfig,
    AgentConfig,
    AgentsConfig,
    KeyConfig,
    KeysConfig,
)
from opengeneral.daemon_client import DEFAULT_DAEMON_HOST, DEFAULT_DAEMON_PORT
from opengeneral.keyring_store import delete_secret, get_secret, set_secret
from opengeneral.provider_factory import create_provider
from opengeneral.providers import ChatProvider
from opengeneral.personas import AgentPersona, PersonaRegistry
from opengeneral.runtime import AgentRuntime


@dataclass
class RunningAgent:
    config: AgentConfig
    action_plane: ActionPlaneConfig
    persona: AgentPersona
    runtime: AgentRuntime
    agent: GeneralPurposeAgent
    provider: ChatProvider
    status: str = "idle"
    last_error: str | None = None


class AgentManager:
    def __init__(self, connector: ActionPlaneConnector | None = None) -> None:
        self.connector = connector or MCPActionPlaneConnector()
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
        # The Action Plane is connected lazily, per agent turn (see GeneralPurposeAgent),
        # not held open at spawn — so spawning never depends on the Action Plane being up.
        runtime = AgentRuntime(
            manifest=persona.manifest,
            connector=self.connector,
            endpoint=action_plane.endpoint,
            action_plane=action_plane.name,
            identity=config.agent_id,
            agent_name=config.name,
        )
        keys_config = KeysConfig.from_path(DEFAULT_KEYS_CONFIG_PATH)
        key_config = keys_config.keys.get(config.key)
        if key_config is None:
            raise ValueError(f"Key not found: {config.key}")
        secret = get_secret(config.key) if key_config.provider_type != "static" else ""
        provider = create_provider(key_config, secret, config.model)
        running = RunningAgent(
            config=config,
            action_plane=action_plane,
            persona=persona,
            runtime=runtime,
            agent=create_agent(persona, runtime, provider),
            provider=provider,
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
            "key": running.config.key,
            "model": running.config.model,
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

    # --- Personas: resolved by the daemon so it is the single source of truth
    # (bundled defaults today; daemon-owned custom personas later). The CLI is a
    # thin client and never reads the persona files itself.

    def list_personas(self) -> list[dict[str, str]]:
        return [
            {"tag": persona.tag, "description": persona.description}
            for persona in PersonaRegistry().list_personas()
        ]

    def show_persona(self, tag: str) -> dict[str, Any]:
        persona = PersonaRegistry().load(tag)
        return {
            "tag": persona.tag,
            "description": persona.description,
            "agent_id": persona.manifest.agent_id,
            "capabilities": [
                {"capability_id": cap.capability_id, "description": cap.description}
                for cap in persona.manifest.capabilities
            ],
        }

    # --- Keys: daemon-owned so the secret is written and read by the same principal
    # (the daemon). Metadata lives in keys.json; the secret in the daemon's keyring.
    # Secrets are inbound-only — there is deliberately no "get secret" method.

    def add_key(
        self, name: str, provider_type: str, base_url: str | None, secret: str
    ) -> dict[str, str | None]:
        config = KeysConfig.from_path(DEFAULT_KEYS_CONFIG_PATH)
        if name in config.keys:
            raise ValueError(f"API key already exists: {name}")
        keys = dict(config.keys)
        keys[name] = KeyConfig(name, provider_type, base_url)
        KeysConfig(keys=keys).write(DEFAULT_KEYS_CONFIG_PATH)
        if provider_type != "static":
            set_secret(name, secret)
        return {"name": name, "type": provider_type, "base_url": base_url}

    def list_keys(self) -> list[dict[str, str | None]]:
        config = KeysConfig.from_path(DEFAULT_KEYS_CONFIG_PATH)
        return [
            {"name": key.name, "type": key.provider_type, "base_url": key.base_url}
            for key in config.keys.values()
        ]

    def show_key(self, name: str) -> dict[str, str | None]:
        config = KeysConfig.from_path(DEFAULT_KEYS_CONFIG_PATH)
        key = config.keys.get(name)
        if key is None:
            raise ValueError(f"API key not found: {name}")
        return {"name": key.name, "type": key.provider_type, "base_url": key.base_url}

    def remove_key(self, name: str) -> dict[str, str]:
        config = KeysConfig.from_path(DEFAULT_KEYS_CONFIG_PATH)
        if name not in config.keys:
            raise ValueError(f"API key not found: {name}")
        keys = dict(config.keys)
        del keys[name]
        KeysConfig(keys=keys).write(DEFAULT_KEYS_CONFIG_PATH)
        delete_secret(name)
        return {"name": name}

    # --- Action planes: daemon-owned (action-planes.json in the daemon's home).

    def add_action_plane(self, name: str, endpoint: str) -> dict[str, str]:
        config = ActionPlanesConfig.from_path(DEFAULT_ACTION_PLANES_CONFIG_PATH)
        action_planes = dict(config.action_planes)
        action_planes[name] = ActionPlaneConfig(name, endpoint)
        ActionPlanesConfig(action_planes=action_planes).write(DEFAULT_ACTION_PLANES_CONFIG_PATH)
        return {"name": name, "endpoint": endpoint}

    def list_action_planes(self) -> list[dict[str, str]]:
        config = ActionPlanesConfig.from_path(DEFAULT_ACTION_PLANES_CONFIG_PATH)
        return [
            {"name": plane.name, "endpoint": plane.endpoint}
            for plane in config.action_planes.values()
        ]

    def show_action_plane(self, name: str) -> dict[str, str]:
        config = ActionPlanesConfig.from_path(DEFAULT_ACTION_PLANES_CONFIG_PATH)
        plane = config.action_planes.get(name)
        if plane is None:
            raise ValueError(f"Action plane not found: {name}")
        return {"name": plane.name, "endpoint": plane.endpoint}

    def remove_action_plane(self, name: str) -> dict[str, str]:
        config = ActionPlanesConfig.from_path(DEFAULT_ACTION_PLANES_CONFIG_PATH)
        if name not in config.action_planes:
            raise ValueError(f"Action plane not found: {name}")
        action_planes = dict(config.action_planes)
        del action_planes[name]
        ActionPlanesConfig(action_planes=action_planes).write(DEFAULT_ACTION_PLANES_CONFIG_PATH)
        return {"name": name}


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
        self._serving = threading.Event()
        self._shutdown_requested = threading.Event()
        super().__init__((host, port), DaemonRequestHandler)

    def serve_forever(self, poll_interval: float = 0.5) -> None:
        # Single-use: once request_shutdown() has been called on an instance,
        # serve_forever() is permanently a no-op for that instance. Construct a
        # fresh OpenGeneralDaemon to serve again.
        if self._shutdown_requested.is_set():
            return
        self._serving.set()
        try:
            super().serve_forever(poll_interval)
        finally:
            self._serving.clear()

    def request_shutdown(self) -> None:
        """Idempotent, deadlock-safe shutdown request.

        Safe to call from any thread, at any time — before serve_forever, during,
        or after. Pre-serve callers just mark the daemon so serve_forever returns
        immediately when it would otherwise start.
        """
        already = self._shutdown_requested.is_set()
        self._shutdown_requested.set()
        if already or not self._serving.is_set():
            return
        # Non-daemon so the worker is allowed to finish even if the main thread
        # is about to exit serve_forever and return from serve().
        threading.Thread(target=self.shutdown, daemon=False).start()

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
            self.request_shutdown()
            return {"status": "stopping"}
        if method == "agent.spawn":
            return asyncio.run(
                self.manager.spawn(
                    AgentConfig(
                        name=params["name"],
                        agent_id=params["id"],
                        persona_tag=params["persona"],
                        action_plane=params["action_plane"],
                        key=params["key"],
                        model=params["model"],
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
        if method == "keys.add":
            return self.manager.add_key(
                params["name"], params["type"], params.get("base_url"), params.get("secret", "")
            )
        if method == "keys.list":
            return self.manager.list_keys()
        if method == "keys.show":
            return self.manager.show_key(params["name"])
        if method == "keys.remove":
            return self.manager.remove_key(params["name"])
        if method == "personas.list":
            return self.manager.list_personas()
        if method == "personas.show":
            return self.manager.show_persona(params["tag"])
        if method == "action_planes.add":
            return self.manager.add_action_plane(params["name"], params["endpoint"])
        if method == "action_planes.list":
            return self.manager.list_action_planes()
        if method == "action_planes.show":
            return self.manager.show_action_plane(params["name"])
        if method == "action_planes.remove":
            return self.manager.remove_action_plane(params["name"])
        raise ValueError(f"Unknown daemon method: {method}")

def serve(host: str = DEFAULT_DAEMON_HOST, port: int = DEFAULT_DAEMON_PORT) -> int:
    """Run the OpenGeneral daemon. Must be called from the main thread.

    Returns the intended process exit code. Returns CONFIG_ERROR_EXIT_CODE (78)
    if persisted agent state cannot be loaded — that exit code is paired with
    `RestartPreventExitStatus=78` in the systemd unit so the supervisor doesn't
    respawn forever on a configuration problem.
    """
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("opengeneral.daemon.serve() must be called from the main thread")

    # Install signal handlers before any slow setup (agent loading can block on
    # keyring/network). Until the daemon exists, a stop signal just records intent
    # so we exit cleanly after setup instead of being killed mid-load by the
    # default handler.
    stop_requested = threading.Event()
    daemon_ref: list[OpenGeneralDaemon | None] = [None]

    def _request_shutdown(*_args: object) -> None:
        stop_requested.set()
        daemon = daemon_ref[0]
        if daemon is not None:
            daemon.request_shutdown()

    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    manager = AgentManager()
    try:
        asyncio.run(manager.load_existing())
    except Exception as error:
        sys.stderr.write(f"OpenGeneral daemon failed to load existing agents: {error}\n")
        sys.stderr.flush()
        return CONFIG_ERROR_EXIT_CODE

    if stop_requested.is_set():
        return 0

    daemon = OpenGeneralDaemon(host, port, manager)
    daemon_ref[0] = daemon
    # A signal could have arrived between constructing the daemon and publishing
    # it above; request_shutdown is idempotent and makes serve_forever a no-op.
    if stop_requested.is_set():
        daemon.request_shutdown()

    try:
        daemon.serve_forever()
    finally:
        daemon.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(serve())
