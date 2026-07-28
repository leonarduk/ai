import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fakes import FakeMCPToolClient
from mcp_client import MCPToolClient


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
