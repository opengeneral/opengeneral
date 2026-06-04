from __future__ import annotations

from dataclasses import dataclass

from opengeneral.manifest import AgentCapabilityManifest
from opengeneral.skills import AgentSkill


@dataclass(frozen=True)
class PromptContext:
    agent_name: str
    persona_name: str
    manifest: AgentCapabilityManifest
    skills: tuple[AgentSkill, ...]


class PromptAssembler:
    def assemble(self, context: PromptContext) -> str:
        sections = [
            f"Your name is {context.agent_name}.",
            f"You are operating as a {context.persona_name} agent.",
            "",
            "You are designed to help with:",
        ]
        if context.manifest.capabilities:
            sections.extend(
                f"- {capability.description}"
                for capability in context.manifest.capabilities
            )
        else:
            sections.append("- General user goals and conversation.")

        sections.extend(["", "You have these skills available:"])
        if context.skills:
            sections.extend(
                f"- {skill.name}: {skill.description}"
                for skill in context.skills
            )
        else:
            sections.append("- No additional skills are loaded.")

        sections.extend(
            [
                "",
                "Use these skills when they help with the user's request. Keep responses focused on the user's goal.",
            ]
        )
        return "\n".join(sections)
