from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from opengeneral.config import OPENGENERAL_HOME

BUNDLED_SKILLS_DIR = Path("skills")
USER_SKILLS_DIR = OPENGENERAL_HOME / "skills"


@dataclass(frozen=True)
class AgentSkill:
    name: str
    description: str
    instructions: str
    path: Path


class SkillNotFoundError(ValueError):
    def __init__(self, name: str) -> None:
        super().__init__(f"unknown skill: {name}")
        self.name = name


class SkillRegistry:
    def __init__(self, skills_dirs: list[str | Path] | None = None) -> None:
        self.skills_dirs = [
            Path(path)
            for path in (skills_dirs or [USER_SKILLS_DIR, BUNDLED_SKILLS_DIR])
        ]

    def list_skills(self) -> list[AgentSkill]:
        skills = []
        for directory in self.skills_dirs:
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*/SKILL.md")):
                skills.append(parse_skill(path))
        return skills

    def load(self, name: str) -> AgentSkill:
        for directory in self.skills_dirs:
            path = directory / name / "SKILL.md"
            if path.exists():
                return parse_skill(path)
        raise SkillNotFoundError(name)

    def load_many(self, names: tuple[str, ...]) -> tuple[AgentSkill, ...]:
        return tuple(self.load(name) for name in names)


def parse_skill(path: str | Path) -> AgentSkill:
    skill_path = Path(path)
    text = skill_path.read_text(encoding="utf-8")
    metadata, instructions = _split_frontmatter(text)
    name = metadata.get("name")
    description = metadata.get("description")
    if name is None:
        raise ValueError(f"Skill is missing frontmatter field: name ({skill_path})")
    if description is None:
        raise ValueError(f"Skill is missing frontmatter field: description ({skill_path})")
    return AgentSkill(
        name=name,
        description=description,
        instructions=instructions.strip(),
        path=skill_path,
    )


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        raise ValueError("Skill is missing YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("Skill frontmatter is not closed")
    raw_metadata = text[4:end]
    body = text[end + len("\n---\n"):]
    metadata = {}
    for line in raw_metadata.splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"Invalid skill frontmatter line: {line}")
        metadata[key.strip()] = value.strip().strip('"')
    return metadata, body
