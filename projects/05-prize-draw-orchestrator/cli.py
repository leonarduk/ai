#!/usr/bin/env python3
"""CLI entry point for the prize-draw orchestrator.

Usage:
    python cli.py --once --dry-run
    python cli.py --interval-minutes 60
"""

from __future__ import annotations

import argparse
import logging

from config import Config
from llm_providers import build_llm_provider
from mcp_client import StdioMCPToolClient
from orchestrator import run_forever, run_once

logger = logging.getLogger("prize_draw_orchestrator")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single pass and exit (default: loop forever)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
        help="Log what would be entered without submitting (default: on, per DRY_RUN env var)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Disable dry-run and actually submit entries (overrides DRY_RUN=true)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    config = Config.from_env()
    dry_run = config.dry_run
    if args.live:
        dry_run = False
    elif args.dry_run:
        dry_run = True

    if not dry_run:
        logger.warning("Running in LIVE mode: eligible draws will actually be entered.")

    llm = build_llm_provider(config)
    if config.llm_provider.strip().lower() != "ollama":
        logger.warning(
            "LLM_PROVIDER=%s: competition content (and any personal data in it) will be sent "
            "to %s's hosted API for reasoning.",
            config.llm_provider,
            config.llm_provider,
        )

    if not config.mcp_server_command:
        raise SystemExit(
            "MCP_SERVER_COMMAND is not set. Point it at the issue #22 MCP server's entry point "
            "(see .env.example)."
        )
    mcp_client = StdioMCPToolClient(
        command=config.mcp_server_command, args=config.mcp_server_args
    )

    if args.once:
        run_once(
            mcp_client,
            llm,
            config.criteria,
            dry_run=dry_run,
            confirm_personal_data=config.confirm_personal_data,
        )
    else:
        run_forever(
            mcp_client,
            llm,
            config.criteria,
            interval_minutes=config.interval_minutes,
            dry_run=dry_run,
            confirm_personal_data=config.confirm_personal_data,
        )


if __name__ == "__main__":
    main()
