from __future__ import annotations

from typing import Mapping, Protocol

from opengeneral.mcp import MCPClient


class ActionPlaneConnector(Protocol):
    async def connect(self, endpoint: str, identity: str) -> Mapping[str, MCPClient]: ...


class EmptyActionPlaneConnector:
    async def connect(self, endpoint: str, identity: str) -> Mapping[str, MCPClient]:
        return {}
