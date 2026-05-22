from __future__ import annotations

import pytest
from jsonschema import ValidationError

from opengeneral.manifest import AgentCapabilityManifest


def test_manifest_accepts_minimal_shape() -> None:
    manifest = AgentCapabilityManifest.from_mapping(
        {"id": "org:example/agent:minimal-v1", "capabilities": []}
    )

    assert manifest.agent_id == "org:example/agent:minimal-v1"
    assert manifest.capabilities == ()


def test_manifest_accepts_declared_capabilities() -> None:
    manifest = AgentCapabilityManifest.from_mapping(
        {
            "id": "org:example/agent:coding-v1",
            "capabilities": [
                {
                    "id": "files_editing",
                    "description": "Can inspect and modify files in a project workspace.",
                }
            ],
        }
    )

    assert manifest.capabilities[0].capability_id == "files_editing"


def test_manifest_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AgentCapabilityManifest.from_mapping(
            {
                "id": "org:example/agent:minimal-v1",
                "capabilities": [],
                "embedded_tools": ["bash"],
            }
        )
