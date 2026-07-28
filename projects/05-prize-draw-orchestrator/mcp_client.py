"""Client interface for calling the prize-draw MCP server's tools.

This module defines a small, generic protocol (`MCPToolClient`) for calling
named MCP tools with a dict of arguments and getting a dict back — the same
shape as the real Model Context Protocol's `ClientSession.call_tool`. The
orchestrator (`orchestrator.py`) is written against this protocol only, so it
does not care whether it's talking to a stub, a fake used in tests, or a real
MCP server subprocess.

As of this writing, issue #22 (the MCP server exposing `search_draws`,
`parse_entry_page`, `submit_entry`, `check_log`) has not been merged into
`main`, so `StdioMCPToolClient` below is a genuine MCP stdio client
implementation (using the official `mcp` Python SDK, the same package the
other servers in `projects/01-mcp-server-suite` are built on) but has not
been exercised against a live server. Once issue #22 lands, point
`MCP_SERVER_COMMAND` / `MCP_SERVER_ARGS` at its entry point and this client
should work unmodified, since it only depends on the tool-call contract
documented in the issue.
"""

from __future__ import annotations

import json
from typing import Any, Protocol


class MCPToolError(RuntimeError):
    """Raised when an MCP tool call fails or returns an unusable result."""


class MCPToolClient(Protocol):
    """Minimal interface for calling MCP tools by name.

    Any implementation — a stub, a test fake, or a real MCP client session —
    only needs to satisfy this one method.
    """

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call the named tool with `arguments` and return its result as a dict."""
        ...


class StdioMCPToolClient:
    """Calls tools on a real MCP server process over stdio.

    Connects lazily on first use and reuses the connection for subsequent
    calls. Requires the `mcp` package (see requirements.txt).
    """

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ):
        """Store the server subprocess command/args/env for later lazy connection."""
        self.command = command
        self.args = args or []
        self.env = env

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Run one MCP tool call in a short-lived stdio session.

        A fresh session per call keeps this client simple and safe to use
        from a synchronous orchestrator loop; it costs a process spawn per
        call, which is acceptable for the polling cadence this tool runs at
        (see README for scheduling guidance).
        """
        import asyncio

        return asyncio.run(self._call_tool_async(name, arguments))

    async def _call_tool_async(
        self, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except (
            ImportError
        ) as exc:  # pragma: no cover - exercised only without the mcp extra installed
            raise MCPToolError(
                "The 'mcp' package is required for StdioMCPToolClient. Install it with "
                "`pip install mcp` (see requirements.txt)."
            ) from exc

        server_params = StdioServerParameters(
            command=self.command, args=self.args, env=self.env
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments=arguments)

        if getattr(result, "isError", False):
            raise MCPToolError(f"MCP tool '{name}' returned an error: {result}")

        structured = getattr(result, "structuredContent", None)
        if isinstance(structured, dict):
            return structured

        for block in getattr(result, "content", []):
            text = getattr(block, "text", None)
            if text:
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"raw": text}
        return {}
