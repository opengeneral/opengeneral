from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from opengeneral.config import OPENGENERAL_HOME, bundled_data_dir
from opengeneral.manifest import AgentCapabilityManifest

BUNDLED_PERSONAS_DIR = bundled_data_dir("personas")
USER_PERSONAS_DIR = OPENGENERAL_HOME / "personas"


@dataclass(frozen=True)
class AgentPersona:
    tag: str
    path: Path
    manifest: AgentCapabilityManifest

    @property
    def description(self) -> str:
        if self.manifest.description:
            return self.manifest.description
        value = self.manifest.extensions.get("opengeneral.description")
        return str(value) if value else "agent persona"


class PersonaNotFoundError(ValueError):
    def __init__(self, tag: str) -> None:
        super().__init__(f"unknown persona: {tag}")
        self.tag = tag


class PersonaRegistry:
    def __init__(self, personas_dirs: list[str | Path] | None = None) -> None:
        self.personas_dirs = [
            Path(path)
            for path in (personas_dirs or [USER_PERSONAS_DIR, BUNDLED_PERSONAS_DIR])
        ]

    def list_personas(self) -> list[AgentPersona]:
        personas = {}
        for directory in reversed(self.personas_dirs):
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.json")):
                personas[path.stem] = self._load_path(path.stem, path)
        return [personas[tag] for tag in sorted(personas)]

    def load(self, tag: str) -> AgentPersona:
        for directory in self.personas_dirs:
            path = directory / f"{tag}.json"
            if path.exists():
                return self._load_path(tag, path)
        raise PersonaNotFoundError(tag)

    def _load_path(self, tag: str, path: Path) -> AgentPersona:
        return AgentPersona(
            tag=tag,
            path=path,
            manifest=AgentCapabilityManifest.from_path(path),
        )
