"""OpenGeneral: a minimal general-purpose agent runtime."""

from opengeneral.agent import GeneralPurposeAgent
from opengeneral.manifest import AgentCapability, AgentCapabilityManifest
from opengeneral.runtime import AgentRuntime

__all__ = [
    "AgentCapabilityManifest",
    "AgentCapability",
    "AgentRuntime",
    "GeneralPurposeAgent",
]
