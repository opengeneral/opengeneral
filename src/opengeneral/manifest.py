from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_MANIFEST_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["id", "capabilities"],
    "properties": {
        "id": {"type": "string"},
        "version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"},
        "capabilities": {
            "type": "array",
            "items": {"$ref": "#/$defs/capability"},
        },
        "extensions": {"type": "object"},
    },
    "$defs": {
        "capability": {
            "type": "object",
            "required": ["id", "description"],
            "properties": {
                "id": {"type": "string"},
                "description": {"type": "string"},
            },
            "additionalProperties": False,
        }
    },
    "additionalProperties": False,
}


@dataclass(frozen=True)
class AgentCapability:
    capability_id: str
    description: str

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> AgentCapability:
        return cls(
            capability_id=value["id"],
            description=value["description"],
        )


@dataclass(frozen=True)
class AgentCapabilityManifest:
    agent_id: str
    version: str | None
    capabilities: tuple[AgentCapability, ...]
    extensions: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> AgentCapabilityManifest:
        Draft202012Validator(_MANIFEST_SCHEMA).validate(value)
        return cls(
            agent_id=value["id"],
            version=value.get("version"),
            capabilities=tuple(
                AgentCapability.from_mapping(capability)
                for capability in value["capabilities"]
            ),
            extensions=dict(value.get("extensions", {})),
        )

    @classmethod
    def from_path(cls, path: str | Path) -> AgentCapabilityManifest:
        with Path(path).open("r", encoding="utf-8") as file:
            return cls.from_mapping(json.load(file))
