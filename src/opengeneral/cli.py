from __future__ import annotations

import argparse
import getpass
import subprocess
import sys
from uuid import uuid4

from opengeneral.config import (
    DEFAULT_ACTION_PLANE,
    DEFAULT_ACTION_PLANES_CONFIG_PATH,
    DEFAULT_AGENTS_CONFIG_PATH,
    DEFAULT_KEYS_CONFIG_PATH,
    SUPPORTED_PROVIDER_TYPES,
    ActionPlaneConfig,
    ActionPlanesConfig,
    AgentsConfig,
    KeyConfig,
    KeysConfig,
)
from opengeneral.daemon_client import DAEMON_NOT_RUNNING, DaemonClient, DaemonUnavailableError
from opengeneral.keyring_store import delete_secret, set_secret
from opengeneral.personas import PersonaNotFoundError, PersonaRegistry
from opengeneral.runner import AgentChatRunner


def create_agent_id(persona_tag: str) -> str:
    return f"{persona_tag}-{uuid4().hex[:12]}"


def prompt(label: str) -> str:
    return input(f"{label}: ").strip()


def choose_provider_type() -> str:
    print("Select a provider:")
    for index, provider_type in enumerate(SUPPORTED_PROVIDER_TYPES, 1):
        print(f"  {index}. {provider_type}")
    choice = prompt("Provider")
    if choice.isdigit():
        selected = int(choice)
        if 1 <= selected <= len(SUPPORTED_PROVIDER_TYPES):
            return SUPPORTED_PROVIDER_TYPES[selected - 1]
    if choice in SUPPORTED_PROVIDER_TYPES:
        return choice
    raise ValueError(f"Unknown provider: {choice}")


def choose_key(config: KeysConfig, provider_type: str) -> str:
    candidates = config.for_provider(provider_type)
    if candidates:
        print(f"Select an API key for {provider_type}:")
        for index, key in enumerate(candidates, 1):
            print(f"  {index}. {key.name}")
        print(f"  {len(candidates) + 1}. Add a new API key")
        choice = prompt("API key")
        if choice.isdigit():
            selected = int(choice)
            if 1 <= selected <= len(candidates):
                return candidates[selected - 1].name
            if selected == len(candidates) + 1:
                return add_key_interactively(config, provider_type)
        if choice in config.keys and config.keys[choice].provider_type == provider_type:
            return choice
        raise ValueError(f"Unknown API key: {choice}")
    return add_key_interactively(config, provider_type)


def add_key_interactively(config: KeysConfig, provider_type: str) -> str:
    name = prompt("API key name")
    if not name:
        raise ValueError("API key name is required.")
    if name in config.keys:
        raise ValueError(f"API key already exists: {name}")
    secret = getpass.getpass("API key secret: ")
    if not secret:
        raise ValueError("API key secret is required.")
    base_url = prompt("Base URL (optional, blank for default)") or None
    keys = dict(config.keys)
    keys[name] = KeyConfig(name, provider_type, base_url)
    KeysConfig(keys).write(DEFAULT_KEYS_CONFIG_PATH)
    set_secret(name, secret)
    return name


def start_agent(
    persona_tag: str,
    action_plane: str,
    key: str | None,
    model: str | None,
    agent_name: str | None,
) -> str:
    persona = PersonaRegistry().load(persona_tag)
    action_planes_config = ActionPlanesConfig.from_path(DEFAULT_ACTION_PLANES_CONFIG_PATH)
    if action_plane not in action_planes_config.action_planes:
        return f"Action plane not found: {action_plane}"

    agents_config = AgentsConfig.from_path(DEFAULT_AGENTS_CONFIG_PATH)
    if agent_name is None:
        return f"Agent name is required. Use: opengeneral spawn --persona {persona.tag} --name <name>"
    name = agent_name
    if name in agents_config.agents:
        return f"Agent already exists: {name}"

    keys_config = KeysConfig.from_path(DEFAULT_KEYS_CONFIG_PATH)
    if key is None:
        provider_type = choose_provider_type()
        key = choose_key(keys_config, provider_type)
    elif key not in keys_config.keys:
        return f"API key not found: {key}"

    model = model or prompt("Model")
    if not model:
        return "Model is required."

    result = DaemonClient().spawn_agent(name, persona.tag, action_plane, key, model, create_agent_id(persona.tag))
    return (
        f"Spawned agent {result['name']} ({result['id']}) from persona "
        f"{result['persona']} via action plane {result['action_plane']} using key {result['key']}"
    )


def render_agents() -> str:
    agents = DaemonClient().list_agents()
    lines = ["Agents:"]
    if not agents:
        lines.append("  (none)")
    for agent in agents:
        lines.append(
            f"  {agent['name']}  {agent['id']}  {agent['persona']}  "
            f"{agent['action_plane']}  {agent['key']}  {agent['model']}"
        )
    return "\n".join(lines)


def show_agent(name: str) -> str:
    agent = DaemonClient().show_agent(name)
    lines = [
        f"Agent: {agent['name']}",
        f"ID: {agent['id']}",
        f"Persona: {agent['persona']}",
        f"Action Plane identity: {agent['id']}",
        f"Action plane: {agent['action_plane']}",
        f"Key: {agent['key']}",
        f"Model: {agent['model']}",
        f"Status: {agent['status']}",
    ]
    if agent.get("last_error") is not None:
        lines.append(f"Last error: {agent['last_error']}")
    return "\n".join(lines)


def remove_agent(name: str) -> str:
    result = DaemonClient().remove_agent(name)
    return f"Removed agent {result['name']} ({result['id']})"


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


def render_keys() -> str:
    config = KeysConfig.from_path(DEFAULT_KEYS_CONFIG_PATH)
    lines = [f"Keys config: {DEFAULT_KEYS_CONFIG_PATH}", "", "API keys:"]
    if not config.keys:
        lines.append("  (none)")
    for key in config.keys.values():
        lines.append(f"  {key.name}  {key.provider_type}")
    return "\n".join(lines)


def show_key(name: str) -> str:
    config = KeysConfig.from_path(DEFAULT_KEYS_CONFIG_PATH)
    key = config.keys.get(name)
    if key is None:
        return f"API key not found: {name}"
    lines = [
        f"API key: {key.name}",
        f"Type: {key.provider_type}",
    ]
    if key.base_url is not None:
        lines.append(f"Base URL: {key.base_url}")
    return "\n".join(lines)


def add_key(name: str, provider_type: str, base_url: str | None) -> str:
    if provider_type not in SUPPORTED_PROVIDER_TYPES:
        return f"Unknown provider type: {provider_type}"
    config = KeysConfig.from_path(DEFAULT_KEYS_CONFIG_PATH)
    if name in config.keys:
        return f"API key already exists: {name}"
    secret = getpass.getpass("API key secret: ")
    if not secret:
        return "API key secret is required."
    keys = dict(config.keys)
    keys[name] = KeyConfig(name, provider_type, base_url)
    KeysConfig(keys=keys).write(DEFAULT_KEYS_CONFIG_PATH)
    set_secret(name, secret)
    return f"Added API key {name} ({provider_type})"


def remove_key(name: str) -> str:
    config = KeysConfig.from_path(DEFAULT_KEYS_CONFIG_PATH)
    if name not in config.keys:
        return f"API key not found: {name}"
    keys = dict(config.keys)
    del keys[name]
    KeysConfig(keys=keys).write(DEFAULT_KEYS_CONFIG_PATH)
    delete_secret(name)
    return f"Removed API key {name}"


def render_daemon_status() -> str:
    result = DaemonClient().status()
    return f"OpenGeneral daemon {result['status']} ({result['agents']} agents)"


def start_daemon() -> str:
    try:
        DaemonClient().status()
    except DaemonUnavailableError:
        subprocess.Popen(
            [sys.executable, "-m", "opengeneral.daemon"],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return "Started OpenGeneral daemon"
    return "OpenGeneral daemon already running"


def stop_daemon() -> str:
    DaemonClient().stop()
    return "Stopped OpenGeneral daemon"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the OpenGeneral reference agent.")
    subparsers = parser.add_subparsers(dest="command")

    personas = subparsers.add_parser("personas", help="Inspect available personas.")
    personas_subparsers = personas.add_subparsers(dest="personas_command", required=True)
    personas_subparsers.add_parser("list", help="List known personas.")
    personas_show = personas_subparsers.add_parser("show", help="Show a persona.")
    personas_show.add_argument("persona")

    keys = subparsers.add_parser("keys", help="Manage API keys stored in the OS keyring.")
    keys_subparsers = keys.add_subparsers(dest="keys_command", required=True)
    keys_subparsers.add_parser("list", help="List API keys.")
    keys_show = keys_subparsers.add_parser("show", help="Show an API key.")
    keys_show.add_argument("name")
    keys_remove = keys_subparsers.add_parser("remove", help="Remove an API key.")
    keys_remove.add_argument("name")
    keys_add = keys_subparsers.add_parser("add", help="Add an API key (prompts for the secret).")
    keys_add.add_argument("name")
    keys_add.add_argument("--type", choices=SUPPORTED_PROVIDER_TYPES, required=True)
    keys_add.add_argument("--base-url")

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

    daemon = subparsers.add_parser("daemon", help="Manage the OpenGeneral daemon.")
    daemon_subparsers = daemon.add_subparsers(dest="daemon_command", required=True)
    daemon_subparsers.add_parser("start", help="Start the daemon.")
    daemon_subparsers.add_parser("status", help="Show daemon status.")
    daemon_subparsers.add_parser("stop", help="Stop the daemon.")

    talk = subparsers.add_parser("talk", help="Open a chat with a spawned agent.")
    talk.add_argument("name")

    spawn = subparsers.add_parser("spawn", help="Spawn an agent from a persona.")
    spawn.add_argument("--persona", required=True)
    spawn.add_argument("--name", required=True)
    spawn.add_argument("--action-plane", default=DEFAULT_ACTION_PLANE)
    spawn.add_argument("--key")
    spawn.add_argument("--model")

    args = parser.parse_args()

    try:
        if args.command == "personas":
            if args.personas_command == "list":
                print(render_personas())
                return
            print(render_persona(args.persona))
            return

        if args.command == "keys":
            if args.keys_command == "list":
                print(render_keys())
                return
            if args.keys_command == "show":
                print(show_key(args.name))
                return
            if args.keys_command == "remove":
                print(remove_key(args.name))
                return
            print(add_key(args.name, args.type, args.base_url))
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

        if args.command == "daemon":
            if args.daemon_command == "start":
                print(start_daemon())
                return
            if args.daemon_command == "status":
                print(render_daemon_status())
                return
            print(stop_daemon())
            return

        if args.command == "talk":
            AgentChatRunner(args.name, DaemonClient()).chat(sys.stdin, sys.stdout)
            return

        if args.command == "spawn":
            print(start_agent(args.persona, args.action_plane, args.key, args.model, args.name))
            return

        parser.print_help()
    except DaemonUnavailableError:
        print(DAEMON_NOT_RUNNING)
    except PersonaNotFoundError as error:
        print(f"Persona not found: {error.tag}")
    except ValueError as error:
        print(error)
    except RuntimeError as error:
        print(error)


if __name__ == "__main__":
    main()
