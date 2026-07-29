"""Test fakes for the MCP tool client and LLM provider interfaces.

These implement the same protocols as the real `StdioMCPToolClient` and the
real `OllamaProvider`/`DeepSeekProvider`/`ClaudeProvider`, so orchestrator
tests never touch the network or spawn a subprocess.
"""

from __future__ import annotations

from typing import Any


class FakeMCPToolClient:
    """In-memory stand-in for the issue #22 MCP server's four tools."""

    def __init__(
        self,
        draws: list[dict[str, Any]] | None = None,
        pages: dict[str, dict[str, Any]] | None = None,
        already_logged: set[str] | None = None,
    ):
        self.draws = draws or []
        self.pages = pages or {}
        self.already_logged = already_logged or set()
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.records: list[dict[str, Any]] = []
        self.submitted: list[dict[str, Any]] = []

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, arguments))

        if name == "search_draws":
            return {"draws": self.draws}

        if name == "parse_entry_page":
            return self.pages.get(arguments["draw_id"], {"content": ""})

        if name == "check_log":
            if "query" in arguments and arguments["query"]:
                draw_id = arguments["query"].get("draw_id")
                return {"seen": draw_id in self.already_logged, "entries": []}
            if "record" in arguments and arguments["record"]:
                self.records.append(arguments["record"])
                return {"ok": True}
            return {"seen": False, "entries": []}

        if name == "submit_entry":
            self.submitted.append(arguments)
            return {"status": "dry_run" if arguments.get("dry_run") else "submitted"}

        raise ValueError(f"Unexpected tool call: {name}")


class FakeLLMProvider:
    """Returns pre-scripted JSON responses, keyed by call order or a fixed value."""

    name = "fake"

    def __init__(
        self,
        responses: list[dict[str, Any]] | None = None,
        fixed_response: dict[str, Any] | None = None,
    ):
        self.responses = list(responses or [])
        self.fixed_response = fixed_response
        self.prompts: list[str] = []

    def generate_json(
        self, prompt: str, schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.prompts.append(prompt)
        if self.fixed_response is not None:
            return dict(self.fixed_response)
        if not self.responses:
            raise AssertionError("FakeLLMProvider ran out of scripted responses")
        return self.responses.pop(0)
