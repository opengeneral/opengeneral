from __future__ import annotations

from dataclasses import dataclass
from typing import TextIO

from opengeneral.action_plane import ActionPlaneConnector
from opengeneral.agent import GeneralPurposeAgent
from opengeneral.config import (
    DEFAULT_ACTION_PLANES_CONFIG_PATH,
    DEFAULT_AGENTS_CONFIG_PATH,
    ActionPlanesConfig,
    AgentsConfig,
)
from opengeneral.personas import PersonaRegistry
from opengeneral.runtime import AgentRuntime

_EXIT_COMMANDS = {"/exit", "/quit"}


@dataclass(frozen=True)
class AgentChatRunner:
    agent_name: str
    agent: GeneralPurposeAgent

    async def respond(self, message: str) -> str:
        return await self.agent.respond(message)

    async def chat(self, input_stream: TextIO, output_stream: TextIO) -> None:
        output_stream.write(f"Talking to {self.agent_name}. Type /exit to leave.\n\n")
        output_stream.flush()
        while True:
            output_stream.write(f"{self.agent_name}> ")
            output_stream.flush()
            message = input_stream.readline()
            if message == "":
                output_stream.write("\n")
                output_stream.flush()
                return
            request = message.strip()
            if request in _EXIT_COMMANDS:
                return
            output_stream.write(await self.respond(request))
            output_stream.write("\n\n")
            output_stream.flush()


async def build_agent_runner(
    agent_name: str,
    connector: ActionPlaneConnector,
) -> AgentChatRunner:
    agents_config = AgentsConfig.from_path(DEFAULT_AGENTS_CONFIG_PATH)
    agent_config = agents_config.agents.get(agent_name)
    if agent_config is None:
        raise ValueError(f"Agent not found: {agent_name}")

    action_planes_config = ActionPlanesConfig.from_path(DEFAULT_ACTION_PLANES_CONFIG_PATH)
    action_plane = action_planes_config.action_planes.get(agent_config.action_plane)
    if action_plane is None:
        raise ValueError(f"Action plane not found: {agent_config.action_plane}")

    persona = PersonaRegistry().load(agent_config.persona_tag)
    clients = await connector.connect(action_plane.endpoint, agent_config.agent_id)
    runtime = AgentRuntime(
        manifest=persona.manifest,
        clients=clients,
        action_plane=action_plane.name,
        identity=agent_config.agent_id,
    )
    return AgentChatRunner(agent_config.name, GeneralPurposeAgent(runtime))
