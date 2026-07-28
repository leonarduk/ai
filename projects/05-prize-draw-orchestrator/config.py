"""Configuration loading for the prize-draw orchestrator.

Reads from environment variables (optionally loaded from a `.env` file next
to this script, matching the convention used in
`projects/04-gmail-inbox-labeler/label_inbox.py`). No secrets are hardcoded
or committed; see `.env.example` for the full list of supported variables.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CRITERIA: dict = {
    "prize_types": [],
    "min_prize_value": 0,
    "entry_methods": ["web_form"],
    "regions": ["UK"],
    "max_days_to_closing": 30,
}


def load_dotenv(env_path: Path | None = None) -> None:
    """Load KEY=VALUE pairs from a `.env` file into `os.environ`.

    Existing environment variables always win (`setdefault`), so real
    environment configuration (e.g. in CI or a container) can never be
    silently overridden by a stray `.env` file.
    """
    path = env_path or Path(__file__).parent / ".env"
    if not path.exists():
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def _load_criteria(raw_path: str | None) -> dict:
    """Load draw-matching criteria from a JSON file, falling back to defaults."""
    if not raw_path:
        return dict(DEFAULT_CRITERIA)
    path = Path(raw_path)
    if not path.exists():
        return dict(DEFAULT_CRITERIA)
    with open(path) as f:
        data = json.load(f)
    merged = dict(DEFAULT_CRITERIA)
    merged.update(data)
    return merged


@dataclass
class Config:
    """Runtime configuration for one orchestrator run."""

    # LLM backend selection ("ollama" is the only backend enabled by default).
    llm_provider: str = "ollama"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-v4-flash"
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"

    # MCP server connection (issue #22's server; see mcp_client.py).
    mcp_server_command: str = ""
    mcp_server_args: list[str] = field(default_factory=list)

    # Safety / automation gates.
    dry_run: bool = True
    confirm_personal_data: bool = False

    # Draw-matching criteria and scheduling.
    criteria: dict = field(default_factory=lambda: dict(DEFAULT_CRITERIA))
    interval_minutes: int = 60

    @classmethod
    def from_env(cls) -> "Config":
        """Build a `Config` from environment variables (after loading `.env`)."""
        load_dotenv()
        mcp_args_raw = os.getenv("MCP_SERVER_ARGS", "")
        mcp_args = (
            json.loads(mcp_args_raw)
            if mcp_args_raw.strip().startswith("[")
            else mcp_args_raw.split()
        )
        interval_minutes = int(os.getenv("RUN_INTERVAL_MINUTES", "60"))
        if interval_minutes <= 0:
            raise ValueError("RUN_INTERVAL_MINUTES must be greater than zero")

        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "ollama"),
            ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3"),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            claude_model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
            mcp_server_command=os.getenv("MCP_SERVER_COMMAND", ""),
            mcp_server_args=mcp_args,
            dry_run=os.getenv("DRY_RUN", "true").strip().lower()
            not in ("false", "0", "no"),
            confirm_personal_data=os.getenv("CONFIRM_PERSONAL_DATA", "false")
            .strip()
            .lower()
            in ("true", "1", "yes"),
            criteria=_load_criteria(os.getenv("CRITERIA_CONFIG_PATH")),
            interval_minutes=interval_minutes,
        )
