from __future__ import annotations

from pathlib import Path

import pytest

from opengeneral.personas import PersonaNotFoundError, PersonaRegistry


def test_persona_registry_loads_persona_by_tag(tmp_path: Path) -> None:
    persona_path = tmp_path / "coding.json"
    persona_path.write_text(
        '{"id":"org:test/agent:coding-v1","capabilities":[]}',
        encoding="utf-8",
    )

    persona = PersonaRegistry([tmp_path]).load("coding")

    assert persona.tag == "coding"
    assert persona.manifest.agent_id == "org:test/agent:coding-v1"


def test_persona_registry_rejects_unknown_tag(tmp_path: Path) -> None:
    with pytest.raises(PersonaNotFoundError):
        PersonaRegistry([tmp_path]).load("missing")
