from __future__ import annotations

import sys
from enum import Enum
from typing import Callable, Optional
from uuid import uuid4

import typer
from typing_extensions import Annotated

from opengeneral import service
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


class ProviderType(str, Enum):
    anthropic = "anthropic"
    openai = "openai"


def create_agent_id(persona_tag: str) -> str:
    return f"{persona_tag}-{uuid4().hex[:12]}"


def prompt(label: str) -> str:
    return typer.prompt(label, default="", show_default=False).strip()


def choose_provider_type() -> str:
    typer.echo("Select a provider:")
    for index, provider_type in enumerate(SUPPORTED_PROVIDER_TYPES, 1):
        typer.echo(f"  {index}. {provider_type}")
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
        typer.echo(f"Select an API key for {provider_type}:")
        for index, key in enumerate(candidates, 1):
            typer.echo(f"  {index}. {key.name}")
        typer.echo(f"  {len(candidates) + 1}. Add a new API key")
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
    secret = typer.prompt("API key secret", hide_input=True)
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
    secret = typer.prompt("API key secret", hide_input=True)
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
    # The running daemon is the source of truth: if it answers the RPC it is up,
    # regardless of whether an OS service manager is even present (foreground runs,
    # containers without systemd). Only fall back to the service manager's view
    # when the daemon isn't reachable.
    agents: int | None
    try:
        agents = DaemonClient().status()["agents"]
    except DaemonUnavailableError:
        agents = None

    try:
        base = service.status()
    except RuntimeError:
        if agents is not None:
            return f"OpenGeneral daemon: running ({agents} agents)"
        raise

    if agents is not None:
        return f"{base} ({agents} agents)"
    return base


def _run(func: Callable[..., str], *args: object, **kwargs: object) -> None:
    try:
        result = func(*args, **kwargs)
        if result is not None:
            typer.echo(result)
    except DaemonUnavailableError:
        typer.echo(DAEMON_NOT_RUNNING)
        raise typer.Exit(1)
    except PersonaNotFoundError as error:
        typer.echo(f"Persona not found: {error.tag}")
        raise typer.Exit(1)
    except (ValueError, RuntimeError) as error:
        typer.echo(str(error))
        raise typer.Exit(1)


app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,
    help="Run the OpenGeneral reference agent.",
)
personas_app = typer.Typer(no_args_is_help=True, help="Inspect available personas.")
keys_app = typer.Typer(no_args_is_help=True, help="Manage API keys stored in the OS keyring.")
action_planes_app = typer.Typer(no_args_is_help=True, help="Manage action plane endpoints.")
agents_app = typer.Typer(no_args_is_help=True, help="Inspect spawned agents.")
daemon_app = typer.Typer(no_args_is_help=True, help="Manage the OpenGeneral daemon.")
app.add_typer(personas_app, name="personas")
app.add_typer(keys_app, name="keys")
app.add_typer(action_planes_app, name="action-planes")
app.add_typer(agents_app, name="agents")
app.add_typer(daemon_app, name="daemon")


@personas_app.command("list", help="List known personas.")
def personas_list_cmd() -> None:
    _run(render_personas)


@personas_app.command("show", help="Show a persona.")
def personas_show_cmd(persona: str) -> None:
    _run(render_persona, persona)


@keys_app.command("list", help="List API keys.")
def keys_list_cmd() -> None:
    _run(render_keys)


@keys_app.command("show", help="Show an API key.")
def keys_show_cmd(name: str) -> None:
    _run(show_key, name)


@keys_app.command("remove", help="Remove an API key and its secret from the OS keyring.")
def keys_remove_cmd(name: str) -> None:
    _run(remove_key, name)


@keys_app.command("add", help="Add an API key (prompts for the secret).")
def keys_add_cmd(
    name: str,
    provider_type: Annotated[ProviderType, typer.Option("--type", help="Provider type.")],
    base_url: Annotated[Optional[str], typer.Option("--base-url", help="Override base URL.")] = None,
) -> None:
    _run(add_key, name, provider_type.value, base_url)


@action_planes_app.command("list", help="List action planes.")
def action_planes_list_cmd() -> None:
    _run(render_action_planes)


@action_planes_app.command("show", help="Show an action plane.")
def action_planes_show_cmd(name: str) -> None:
    _run(show_action_plane, name)


@action_planes_app.command("remove", help="Remove an action plane.")
def action_planes_remove_cmd(name: str) -> None:
    _run(remove_action_plane, name)


@action_planes_app.command("add", help="Add an action plane.")
def action_planes_add_cmd(
    name: str,
    endpoint: Annotated[str, typer.Option("--endpoint", help="MCP endpoint URL.")],
) -> None:
    _run(add_action_plane, name, endpoint)


@agents_app.command("list", help="List spawned agents.")
def agents_list_cmd() -> None:
    _run(render_agents)


@agents_app.command("show", help="Show a spawned agent.")
def agents_show_cmd(name: str) -> None:
    _run(show_agent, name)


@agents_app.command("remove", help="Remove a spawned agent.")
def agents_remove_cmd(name: str) -> None:
    _run(remove_agent, name)


@daemon_app.command("install", help="Register the OpenGeneral daemon with the OS service manager.")
def daemon_install_cmd() -> None:
    _run(service.install)


@daemon_app.command("uninstall", help="Unregister the OpenGeneral daemon from the OS service manager.")
def daemon_uninstall_cmd() -> None:
    _run(service.uninstall)


@daemon_app.command("start", help="Start the daemon via the OS service manager.")
def daemon_start_cmd() -> None:
    _run(service.start)


@daemon_app.command("status", help="Show the daemon's service status.")
def daemon_status_cmd() -> None:
    _run(render_daemon_status)


@daemon_app.command("stop", help="Stop the daemon via the OS service manager.")
def daemon_stop_cmd() -> None:
    _run(service.stop)


@daemon_app.command(
    "run",
    help="Run the daemon in the foreground. Used by the service manager, and as a "
    "manual fallback where no service manager is available (macOS, containers).",
)
def daemon_run_cmd() -> None:
    from opengeneral.daemon import serve

    raise typer.Exit(serve())


@app.command("talk", help="Open a chat with a spawned agent.")
def talk_cmd(name: str) -> None:
    try:
        AgentChatRunner(name, DaemonClient()).chat(sys.stdin, sys.stdout)
    except DaemonUnavailableError:
        typer.echo(DAEMON_NOT_RUNNING)
    except (ValueError, RuntimeError) as error:
        typer.echo(str(error))


@app.command("spawn", help="Spawn an agent from a persona.")
def spawn_cmd(
    persona: Annotated[str, typer.Option("--persona", help="Persona tag.")],
    name: Annotated[str, typer.Option("--name", help="Readable agent name.")],
    action_plane: Annotated[str, typer.Option("--action-plane", help="Configured Action Plane name.")] = DEFAULT_ACTION_PLANE,
    key: Annotated[Optional[str], typer.Option("--key", help="Configured API key name.")] = None,
    model: Annotated[Optional[str], typer.Option("--model", help="Model identifier (e.g. anthropic/claude-opus-4-7).")] = None,
) -> None:
    _run(start_agent, persona, action_plane, key, model, name)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
