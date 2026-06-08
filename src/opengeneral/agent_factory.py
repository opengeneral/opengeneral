from __future__ import annotations

from opengeneral.agent import AgentConstruction, GeneralPurposeAgent
from opengeneral.personas import AgentPersona
from opengeneral.prompt import PromptAssembler, PromptContext
from opengeneral.providers import ChatProvider
from opengeneral.runtime import AgentRuntime
from opengeneral.skills import SkillRegistry


def create_agent(
    persona: AgentPersona,
    runtime: AgentRuntime,
    provider: ChatProvider,
) -> GeneralPurposeAgent:
    manifest = persona.manifest
    if runtime.agent_name is None:
        raise ValueError("agent_name is required to construct an agent")
    skills = SkillRegistry().load_many(manifest.skills)
    assembled_prompt = PromptAssembler().assemble(
        PromptContext(
            agent_name=runtime.agent_name,
            persona_name=persona.tag,
            manifest=manifest,
            skills=skills,
        )
    )
    construction = AgentConstruction(
        skills=skills,
        assembled_prompt=assembled_prompt,
    )
    return GeneralPurposeAgent(runtime, construction, provider)
