from __future__ import annotations

from pathlib import Path

import pytest

from opengeneral.personas import PersonaNotFoundError, PersonaRegistry


def test_persona_registry_loads_persona_by_tag(tmp_path: Path) -> None:
    persona_path = tmp_path / "coder.json"
    persona_path.write_text(
        '{"id":"org:test/persona:coder-v1","capabilities":[],"extensions":{"opengeneral.description":"Coder persona.","opengeneral.skills":["debugging"]}}',
        encoding="utf-8",
    )

    persona = PersonaRegistry([tmp_path]).load("coder")

    assert persona.tag == "coder"
    assert persona.manifest.agent_id == "org:test/persona:coder-v1"
    assert persona.description == "Coder persona."
    assert persona.manifest.skills == ("debugging",)


def test_persona_registry_rejects_unknown_tag(tmp_path: Path) -> None:
    with pytest.raises(PersonaNotFoundError):
        PersonaRegistry([tmp_path]).load("missing")
