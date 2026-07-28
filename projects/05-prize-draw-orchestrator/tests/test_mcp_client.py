import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fakes import FakeMCPToolClient
from mcp_client import MCPToolClient, StdioMCPToolClient


class TestFakeSatisfiesProtocol:
    def test_fake_client_satisfies_the_mcp_tool_client_protocol(self):
        client: MCPToolClient = FakeMCPToolClient(
            draws=[{"draw_id": "d1", "url": "https://x"}]
        )
        result = client.call_tool("search_draws", {"criteria": {}})
        assert result == {"draws": [{"draw_id": "d1", "url": "https://x"}]}

    def test_unknown_tool_name_raises(self):
        client = FakeMCPToolClient()
        try:
            client.call_tool("not_a_real_tool", {})
        except ValueError as exc:
            assert "not_a_real_tool" in str(exc)
        else:
            raise AssertionError("expected ValueError")


@dataclass
class _FakeToolResult:
    isError: bool = False
    structuredContent: Any = None
    content: list = field(default_factory=list)


@dataclass
class _FakeTextBlock:
    text: str


class TestStdioMCPToolClientResultParsing:
    """`_call_tool_async`'s result parsing, exercised without a real subprocess."""

    def _call(self, result: _FakeToolResult) -> dict:
        client = StdioMCPToolClient(command="python", args=["server.py"])

        session = AsyncMock()
        session.initialize = AsyncMock()
        session.call_tool = AsyncMock(return_value=result)
        session_cm = AsyncMock()
        session_cm.__aenter__.return_value = session

        stdio_cm = AsyncMock()
        stdio_cm.__aenter__.return_value = (None, None)

        with patch("mcp.ClientSession", return_value=session_cm), patch(
            "mcp.client.stdio.stdio_client", return_value=stdio_cm
        ):
            return client.call_tool("search_draws", {"criteria": {}})

    def test_prefers_structured_content_over_text_blocks(self):
        result = self._call(
            _FakeToolResult(
                structuredContent={"draws": [{"draw_id": "d1"}]},
                content=[_FakeTextBlock(text="ignored")],
            )
        )
        assert result == {"draws": [{"draw_id": "d1"}]}

    def test_falls_back_to_text_block_json_when_no_structured_content(self):
        result = self._call(
            _FakeToolResult(content=[_FakeTextBlock(text='{"draws": []}')])
        )
        assert result == {"draws": []}
