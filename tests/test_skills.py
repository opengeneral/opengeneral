from __future__ import annotations

from pathlib import Path

import pytest

from opengeneral.skills import SkillNotFoundError, SkillRegistry, parse_skill


def test_parse_skill_reads_frontmatter_and_instructions(tmp_path: Path) -> None:
    path = tmp_path / "SKILL.md"
    path.write_text(
        "---\nname: debugging\ndescription: Use for debugging.\n---\n\n# Debugging\n\nSteps.",
        encoding="utf-8",
    )

    skill = parse_skill(path)

    assert skill.name == "debugging"
    assert skill.description == "Use for debugging."
    assert "Steps." in skill.instructions


def test_parse_skill_requires_name(tmp_path: Path) -> None:
    path = tmp_path / "SKILL.md"
    path.write_text("---\ndescription: Missing name.\n---\n\nBody.", encoding="utf-8")

    with pytest.raises(ValueError, match="name"):
        parse_skill(path)


def test_skill_registry_loads_named_skill(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "debugging"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: debugging\ndescription: Use for debugging.\n---\n\nBody.",
        encoding="utf-8",
    )

    skill = SkillRegistry([tmp_path / "skills"]).load("debugging")

    assert skill.name == "debugging"


def test_skill_registry_rejects_unknown_skill(tmp_path: Path) -> None:
    with pytest.raises(SkillNotFoundError):
        SkillRegistry([tmp_path]).load("missing")
