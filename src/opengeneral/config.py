from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path


def bundled_data_dir(name: str) -> Path:
    """Locate a directory of files shipped with OpenGeneral (e.g. ``personas``,
    ``skills``).

    In a PyInstaller binary the data is unpacked under the bundle (``sys._MEIPASS``,
    populated by ``--add-data``); from source it lives at the repo root. Always an
    absolute path, so resolution never depends on the current working directory.
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / name  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2] / name


OPENGENERAL_HOME = Path(os.environ.get("OPENGENERAL_HOME", "~/.opengeneral")).expanduser()
DEFAULT_ACTION_PLANES_CONFIG_PATH = Path(
    os.environ.get("OPENGENERAL_ACTION_PLANES_CONFIG", OPENGENERAL_HOME / "action-planes.json")
).expanduser()
DEFAULT_AGENTS_CONFIG_PATH = Path(
    os.environ.get("OPENGENERAL_AGENTS_CONFIG", OPENGENERAL_HOME / "agents.json")
).expanduser()
DEFAULT_KEYS_CONFIG_PATH = Path(
    os.environ.get("OPENGENERAL_KEYS_CONFIG", OPENGENERAL_HOME / "keys.json")
).expanduser()
DEFAULT_ACTION_PLANE = "default"
SUPPORTED_PROVIDER_TYPES = ("anthropic", "openai")


@dataclass(frozen=True)
class ActionPlaneConfig:
    name: str
    endpoint: str


@dataclass(frozen=True)
class ActionPlanesConfig:
    action_planes: dict[str, ActionPlaneConfig]

    @classmethod
    def empty(cls) -> ActionPlanesConfig:
        return cls(action_planes={})

    @classmethod
    def from_path(cls, path: str | Path) -> ActionPlanesConfig:
        config_path = Path(path)
        if not config_path.exists():
            return cls.empty()

        with config_path.open("r", encoding="utf-8") as file:
            raw = json.load(file)

        action_planes = {}
        for name, value in raw.get("action_planes", {}).items():
            action_planes[name] = ActionPlaneConfig(
                name=name,
                endpoint=value["endpoint"],
            )
        return cls(action_planes=action_planes)

    def to_mapping(self) -> dict[str, object]:
        return {
            "action_planes": {
                name: {"endpoint": action_plane.endpoint}
                for name, action_plane in self.action_planes.items()
            }
        }

    def write(self, path: str | Path = DEFAULT_ACTION_PLANES_CONFIG_PATH) -> None:
        config_path = Path(path).expanduser()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as file:
            json.dump(self.to_mapping(), file, indent=2)
            file.write("\n")


@dataclass(frozen=True)
class KeyConfig:
    name: str
    provider_type: str
    base_url: str | None = None


@dataclass(frozen=True)
class KeysConfig:
    keys: dict[str, KeyConfig]

    @classmethod
    def empty(cls) -> KeysConfig:
        return cls(keys={})

    @classmethod
    def from_path(cls, path: str | Path) -> KeysConfig:
        config_path = Path(path)
        if not config_path.exists():
            return cls.empty()

        with config_path.open("r", encoding="utf-8") as file:
            raw = json.load(file)

        keys = {}
        for name, value in raw.get("keys", {}).items():
            keys[name] = KeyConfig(
                name=name,
                provider_type=value["type"],
                base_url=value.get("base_url"),
            )
        return cls(keys=keys)

    def for_provider(self, provider_type: str) -> tuple[KeyConfig, ...]:
        return tuple(key for key in self.keys.values() if key.provider_type == provider_type)

    def to_mapping(self) -> dict[str, object]:
        return {
            "keys": {
                name: {
                    "type": key.provider_type,
                    **({"base_url": key.base_url} if key.base_url is not None else {}),
                }
                for name, key in self.keys.items()
            }
        }

    def write(self, path: str | Path = DEFAULT_KEYS_CONFIG_PATH) -> None:
        config_path = Path(path).expanduser()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as file:
            json.dump(self.to_mapping(), file, indent=2)
            file.write("\n")


@dataclass(frozen=True)
class AgentConfig:
    name: str
    agent_id: str
    persona_tag: str
    action_plane: str
    key: str
    model: str


@dataclass(frozen=True)
class AgentsConfig:
    agents: dict[str, AgentConfig]

    @classmethod
    def empty(cls) -> AgentsConfig:
        return cls(agents={})

    @classmethod
    def from_path(cls, path: str | Path) -> AgentsConfig:
        config_path = Path(path)
        if not config_path.exists():
            return cls.empty()

        with config_path.open("r", encoding="utf-8") as file:
            raw = json.load(file)

        agents = {}
        for name, value in raw.get("agents", {}).items():
            agents[name] = AgentConfig(
                name=name,
                agent_id=value["id"],
                persona_tag=value["persona"],
                action_plane=value["action_plane"],
                key=value["key"],
                model=value["model"],
            )
        return cls(agents=agents)

    def latest_for(self, persona_tag: str, action_plane: str | None = None) -> AgentConfig | None:
        for agent in reversed(tuple(self.agents.values())):
            if agent.persona_tag != persona_tag:
                continue
            if action_plane is not None and agent.action_plane != action_plane:
                continue
            return agent
        return None

    def to_mapping(self) -> dict[str, object]:
        return {
            "agents": {
                name: {
                    "id": agent.agent_id,
                    "persona": agent.persona_tag,
                    "action_plane": agent.action_plane,
                    "key": agent.key,
                    "model": agent.model,
                }
                for name, agent in self.agents.items()
            }
        }

    def write(self, path: str | Path = DEFAULT_AGENTS_CONFIG_PATH) -> None:
        config_path = Path(path).expanduser()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as file:
            json.dump(self.to_mapping(), file, indent=2)
            file.write("\n")


def load_default_action_planes_config() -> ActionPlanesConfig:
    return ActionPlanesConfig.from_path(DEFAULT_ACTION_PLANES_CONFIG_PATH)


def load_default_agents_config() -> AgentsConfig:
    return AgentsConfig.from_path(DEFAULT_AGENTS_CONFIG_PATH)


def load_default_keys_config() -> KeysConfig:
    return KeysConfig.from_path(DEFAULT_KEYS_CONFIG_PATH)
