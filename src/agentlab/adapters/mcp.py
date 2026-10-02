"""Future MCP boundary only. No MCP client or transport is implemented yet."""

from typing import Any, Protocol

from agentlab.core.models import ToolSpec


class MCPTransport(Protocol):
    def list_tools(self) -> list[ToolSpec]: ...

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


class MCPTool:
    """Wrap an externally supplied transport; calls pass through the normal trace loop.

    A future integration must handle capability negotiation, authentication,
    deadlines, content blocks, cancellation and untrusted tool results.
    """

    def __init__(self, spec: ToolSpec, transport: MCPTransport):
        self.spec, self.transport = spec, transport

    def invoke(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.transport.call_tool(self.spec.name, arguments)
