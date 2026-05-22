from __future__ import annotations

import argparse
from uuid import uuid4

from opengeneral.config import (
    DEFAULT_ACTION_PLANE,
    DEFAULT_ACTION_PLANES_CONFIG_PATH,
    DEFAULT_AGENTS_CONFIG_PATH,
    ActionPlaneConfig,
    ActionPlanesConfig,
    AgentConfig,
    AgentsConfig,
)
from opengeneral.personas import PersonaNotFoundError, PersonaRegistry

def create_agent_id(persona_tag: str) -> str:
    return f"{persona_tag}-{uuid4().hex[:12]}"


def default_agent_name(persona_tag: str, agents: dict[str, AgentConfig]) -> str:
    if persona_tag not in agents:
        return persona_tag
    index = 2
    while f"{persona_tag}-{index}" in agents:
        index += 1
    return f"{persona_tag}-{index}"


def start_agent(
    persona_tag: str,
    action_plane: str,
    agent_name: str | None,
    token_ref: str | None,
) -> str:
    persona = PersonaRegistry().load(persona_tag)
    action_planes_config = ActionPlanesConfig.from_path(DEFAULT_ACTION_PLANES_CONFIG_PATH)
    if action_plane not in action_planes_config.action_planes:
        return f"Action plane not found: {action_plane}"

    agents_config = AgentsConfig.from_path(DEFAULT_AGENTS_CONFIG_PATH)
    agents = dict(agents_config.agents)
    name = agent_name or default_agent_name(persona.tag, agents)
    if name in agents:
        return f"Agent already exists: {name}"

    agent_id = create_agent_id(persona.tag)
    agents[name] = AgentConfig(
        name=name,
        agent_id=agent_id,
        persona_tag=persona.tag,
        action_plane=action_plane,
        token_ref=token_ref,
    )
    AgentsConfig(agents=agents).write(DEFAULT_AGENTS_CONFIG_PATH)
    return f"Spawned agent {name} ({agent_id}) from persona {persona.tag} via action plane {action_plane}"



def render_agents() -> str:
    config = AgentsConfig.from_path(DEFAULT_AGENTS_CONFIG_PATH)
    lines = [f"Agents config: {DEFAULT_AGENTS_CONFIG_PATH}", "", "Agents:"]
    if not config.agents:
        lines.append("  (none)")
    for agent in config.agents.values():
        lines.append(f"  {agent.name}  {agent.agent_id}  {agent.persona_tag}  {agent.action_plane}")
    return "\n".join(lines)


def show_agent(name: str) -> str:
    config = AgentsConfig.from_path(DEFAULT_AGENTS_CONFIG_PATH)
    agent = config.agents.get(name)
    if agent is None:
        return f"Agent not found: {name}"
    lines = [
        f"Agent: {agent.name}",
        f"ID: {agent.agent_id}",
        f"Persona: {agent.persona_tag}",
        f"Action Plane identity: {agent.agent_id}",
        f"Action plane: {agent.action_plane}",
    ]
    if agent.token_ref is not None:
        lines.append(f"Token: {agent.token_ref}")
    return "\n".join(lines)


def remove_agent(name: str) -> str:
    config = AgentsConfig.from_path(DEFAULT_AGENTS_CONFIG_PATH)
    if name not in config.agents:
        return f"Agent not found: {name}"
    agents = dict(config.agents)
    agent = agents.pop(name)
    AgentsConfig(agents=agents).write(DEFAULT_AGENTS_CONFIG_PATH)
    return f"Removed agent {agent.name} ({agent.agent_id}) from {DEFAULT_AGENTS_CONFIG_PATH}"


def render_personas() -> str:
    personas = PersonaRegistry().list_personas()
    if not personas:
        return "No personas found."
    return "\n".join(f"{persona.tag}\t{persona.description}" for persona in personas)


def render_persona(persona_tag: str) -> str:
    persona = PersonaRegistry().load(persona_tag)
    lines = [f"Persona: {persona.tag}", f"Agent ID: {persona.manifest.agent_id}", ""]
    lines.append("Declared capabilities:")
    if not persona.manifest.capabilities:
        lines.append("  (none)")
    for capability in persona.manifest.capabilities:
        lines.append(f"  {capability.capability_id}  {capability.description}")
    return "\n".join(lines)


def render_action_planes() -> str:
    config = ActionPlanesConfig.from_path(DEFAULT_ACTION_PLANES_CONFIG_PATH)
    lines = [f"Action planes config: {DEFAULT_ACTION_PLANES_CONFIG_PATH}", "", "Action planes:"]
    if not config.action_planes:
        lines.append("  (none)")
    for action_plane in config.action_planes.values():
        lines.append(f"  {action_plane.name}  {action_plane.endpoint}")
    return "\n".join(lines)


def show_action_plane(name: str) -> str:
    config = ActionPlanesConfig.from_path(DEFAULT_ACTION_PLANES_CONFIG_PATH)
    action_plane = config.action_planes.get(name)
    if action_plane is None:
        return f"Action plane not found: {name}"
    return "\n".join(
        [
            f"Action plane: {action_plane.name}",
            f"Endpoint: {action_plane.endpoint}",
        ]
    )


def add_action_plane(name: str, endpoint: str) -> str:
    config = ActionPlanesConfig.from_path(DEFAULT_ACTION_PLANES_CONFIG_PATH)
    action_planes = dict(config.action_planes)
    action_planes[name] = ActionPlaneConfig(name, endpoint)
    ActionPlanesConfig(action_planes=action_planes).write(DEFAULT_ACTION_PLANES_CONFIG_PATH)
    return f"Added action plane {name} to {DEFAULT_ACTION_PLANES_CONFIG_PATH}"


def remove_action_plane(name: str) -> str:
    config = ActionPlanesConfig.from_path(DEFAULT_ACTION_PLANES_CONFIG_PATH)
    if name not in config.action_planes:
        return f"Action plane not found: {name}"
    action_planes = dict(config.action_planes)
    del action_planes[name]
    ActionPlanesConfig(action_planes=action_planes).write(DEFAULT_ACTION_PLANES_CONFIG_PATH)
    return f"Removed action plane {name} from {DEFAULT_ACTION_PLANES_CONFIG_PATH}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the OpenGeneral reference agent.")
    subparsers = parser.add_subparsers(dest="command")

    personas = subparsers.add_parser("personas", help="Inspect available personas.")
    personas_subparsers = personas.add_subparsers(dest="personas_command", required=True)
    personas_subparsers.add_parser("list", help="List known personas.")
    personas_show = personas_subparsers.add_parser("show", help="Show a persona.")
    personas_show.add_argument("persona")

    action_planes = subparsers.add_parser("action-planes", help="Manage action plane endpoints.")
    action_planes_subparsers = action_planes.add_subparsers(
        dest="action_planes_command", required=True
    )
    action_planes_subparsers.add_parser("list", help="List action planes.")
    action_planes_show = action_planes_subparsers.add_parser("show", help="Show an action plane.")
    action_planes_show.add_argument("name")
    action_planes_remove = action_planes_subparsers.add_parser("remove", help="Remove an action plane.")
    action_planes_remove.add_argument("name")
    action_planes_add = action_planes_subparsers.add_parser("add", help="Add an action plane.")
    action_planes_add.add_argument("name")
    action_planes_add.add_argument("--endpoint", required=True)

    agents = subparsers.add_parser("agents", help="Inspect spawned agents.")
    agents_subparsers = agents.add_subparsers(dest="agents_command", required=True)
    agents_subparsers.add_parser("list", help="List spawned agents.")
    agents_show = agents_subparsers.add_parser("show", help="Show a spawned agent.")
    agents_show.add_argument("name")
    agents_remove = agents_subparsers.add_parser("remove", help="Remove a spawned agent.")
    agents_remove.add_argument("name")

    spawn = subparsers.add_parser("spawn", help="Spawn an agent from a persona.")
    spawn.add_argument("--persona", required=True)
    spawn.add_argument("--name")
    spawn.add_argument("--action-plane", default=DEFAULT_ACTION_PLANE)
    spawn.add_argument("--token-ref")
    spawn.add_argument("--token-env")

    args = parser.parse_args()

    try:
        if args.command == "personas":
            if args.personas_command == "list":
                print(render_personas())
                return
            print(render_persona(args.persona))
            return

        if args.command == "action-planes":
            if args.action_planes_command == "list":
                print(render_action_planes())
                return
            if args.action_planes_command == "show":
                print(show_action_plane(args.name))
                return
            if args.action_planes_command == "remove":
                print(remove_action_plane(args.name))
                return
            print(add_action_plane(args.name, args.endpoint))
            return

        if args.command == "agents":
            if args.agents_command == "list":
                print(render_agents())
                return
            if args.agents_command == "show":
                print(show_agent(args.name))
                return
            print(remove_agent(args.name))
            return

        if args.command == "spawn":
            token_ref = args.token_ref
            if args.token_env is not None:
                token_ref = f"env:{args.token_env}"
            print(start_agent(args.persona, args.action_plane, args.name, token_ref))
            return

        parser.print_help()
    except PersonaNotFoundError as error:
        print(f"Persona not found: {error.tag}")


if __name__ == "__main__":
    main()
