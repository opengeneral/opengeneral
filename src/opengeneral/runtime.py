from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from opengeneral.action_plane import ActionPlaneConnector, EmptyActionPlaneConnector
from opengeneral.manifest import AgentCapabilityManifest
from opengeneral.mcp import MCPSession


@dataclass(frozen=True)
class AgentRuntime:
    manifest: AgentCapabilityManifest
    connector: ActionPlaneConnector = EmptyActionPlaneConnector()
    endpoint: str | None = None
    action_plane: str | None = None
    identity: str | None = None
    agent_name: str | None = None

    @asynccontextmanager
    async def action_plane_session(self) -> AsyncIterator[MCPSession]:
        async with self.connector.session(self.endpoint or "", self.identity) as session:
            yield session
