from __future__ import annotations

from opengeneral.manifest import AgentCapabilityManifest
from opengeneral.prompt import PromptAssembler, PromptContext
from opengeneral.skills import AgentSkill


def test_prompt_assembler_separates_agent_name_from_persona() -> None:
    manifest = AgentCapabilityManifest.from_mapping(
        {
            "id": "opengeneral/persona:coder-v1",
            "capabilities": [
                {
                    "id": "files_editing",
                    "description": "Working with project files and workspace content.",
                }
            ],
        }
    )
    skill = AgentSkill("debugging", "Use for debugging.", "Debug carefully.", __file__)

    prompt = PromptAssembler().assemble(
        PromptContext("repo-helper", "coder", manifest, (skill,))
    )

    assert "Your name is repo-helper." in prompt
    assert "You are operating as a coder agent." in prompt
    assert "- Working with project files and workspace content." in prompt
    assert "- debugging: Use for debugging." in prompt
