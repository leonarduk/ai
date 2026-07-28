#!/usr/bin/env python3
"""
MCP Server for prize draw discovery and entry.

Exposes the scraping/parsing/entry/logging mechanics needed to find and
enter prize draws as MCP tools, so an orchestrating client (issue #23,
parent issue #21) can decide what LLM backend to reason with. This server
contains no LLM/provider-specific logic itself:

- search_draws       - poll configured source(s) for candidate draws
- parse_entry_page   - fetch a draw's entry page/feed item, return raw content
- submit_entry       - perform (or dry-run) the entry action for a draw
- check_log          - query/record entries in the local data store
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from mcp.server import Server
from mcp.types import TextContent, Tool

import entry as entry_mod
import sources as sources_mod
from store import PrizeDrawStore, utcnow_iso

REQUEST_TIMEOUT_SECONDS = 15


def load_env() -> None:
    """Load environment variables from a .env file in the project root."""
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as handle:
            for line in handle:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()


load_env()

app = Server("prize-draw-server")

_store: Optional[PrizeDrawStore] = None


def get_store() -> PrizeDrawStore:
    """Return the shared PrizeDrawStore, honouring PRIZE_DRAW_STORE_PATH."""
    global _store
    if _store is None:
        store_path = os.environ.get("PRIZE_DRAW_STORE_PATH")
        _store = PrizeDrawStore(Path(store_path) if store_path else None)
    return _store


def set_store(store: PrizeDrawStore) -> None:
    """Override the shared store (used by tests to point at a temp file)."""
    global _store
    _store = store


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_draws",
            description=(
                "Poll configured source(s) (aggregator sites/RSS feeds) for "
                "candidate prize draws and return raw listings. Newly seen "
                "draws are recorded in the log with status 'discovered' so "
                "check_log can support duplicate avoidance later."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "sources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Names of configured sources to poll (default: "
                            "all configured sources)."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of listings to return.",
                    },
                },
            },
        ),
        Tool(
            name="parse_entry_page",
            description=(
                "Fetch a draw's entry page (or feed item URL) and return its "
                "raw content (HTML/text) plus basic metadata, for the caller "
                "to interpret. Performs no LLM call and no interpretation - "
                "just clean structured input for one. URLs starting with "
                "'mock://' return a canned fixture with no network access, "
                "for demos/tests."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL of the entry page/feed item to fetch.",
                    },
                    "include_html": {
                        "type": "boolean",
                        "description": "Include raw HTML in the response (default: false).",
                        "default": False,
                    },
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="submit_entry",
            description=(
                "Submit (or dry-run) the entry action for a draw, given "
                "already-resolved field values from the caller. Refuses to "
                "submit personal/financial-looking fields without "
                "confirm_personal_data=true, and refuses draws that require "
                "a purchase without confirm_purchase_required=true. Refuses "
                "to re-enter a draw already logged as 'entered'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "draw_id": {
                        "type": "string",
                        "description": "Stable identifier for the draw (see search_draws).",
                    },
                    "entry_method": {
                        "type": "string",
                        "enum": ["web_form", "email", "social"],
                        "description": "How to enter: web form POST, email, or a social action.",
                    },
                    "fields": {
                        "type": "object",
                        "description": (
                            "Resolved field values to submit, e.g. "
                            "{'answer': 'Paris', 'email': 'a@b.com'}."
                        ),
                        "default": {},
                    },
                    "url": {
                        "type": "string",
                        "description": "Entry form URL (required for entry_method=web_form).",
                    },
                    "email_to": {
                        "type": "string",
                        "description": "Recipient address (required for entry_method=email).",
                    },
                    "email_subject": {
                        "type": "string",
                        "description": "Subject line (entry_method=email).",
                    },
                    "email_body": {
                        "type": "string",
                        "description": "Body text (entry_method=email).",
                    },
                    "social_action": {
                        "type": "string",
                        "description": "Action name, e.g. 'follow'/'like'/'retweet' (entry_method=social).",
                    },
                    "requires_purchase": {
                        "type": "boolean",
                        "description": "Whether this draw requires a purchase to enter.",
                        "default": False,
                    },
                    "confirm_purchase_required": {
                        "type": "boolean",
                        "description": "Explicit override to proceed despite requires_purchase.",
                        "default": False,
                    },
                    "confirm_personal_data": {
                        "type": "boolean",
                        "description": "Explicit confirmation to submit personal/financial fields.",
                        "default": False,
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": (
                            "If true (default), log what would be submitted "
                            "without submitting anything."
                        ),
                        "default": True,
                    },
                    "source": {
                        "type": "string",
                        "description": "Source name, for the log entry if the draw isn't already logged.",
                        "default": "unknown",
                    },
                },
                "required": ["draw_id", "entry_method"],
            },
        ),
        Tool(
            name="check_log",
            description=(
                "Query the entry log/data store for previously seen or "
                "entered draws (duplicate avoidance), or record a new "
                "entry/result directly."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "get", "has_seen", "has_entered", "record"],
                        "description": "Which operation to perform.",
                    },
                    "draw_id": {
                        "type": "string",
                        "description": "Draw id (required for get/has_seen/has_entered/record).",
                    },
                    "status": {
                        "type": "string",
                        "enum": [
                            "discovered",
                            "dry_run",
                            "entered",
                            "skipped",
                            "failed",
                        ],
                        "description": "Filter for action=list, or the value to set for action=record.",
                    },
                    "record": {
                        "type": "object",
                        "description": "Full/partial draw record to upsert for action=record.",
                    },
                },
                "required": ["action"],
            },
        ),
    ]


def _json_content(payload: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, indent=2))]


def _handle_search_draws(arguments: dict) -> list[TextContent]:
    names = arguments.get("sources")
    limit = arguments.get("limit")

    listings = sources_mod.poll_sources(names=names)
    if limit is not None:
        listings = listings[:limit]

    store = get_store()
    for listing in listings:
        if not store.has_seen(listing["draw_id"]):
            store.upsert(
                {
                    "draw_id": listing["draw_id"],
                    "source": listing["source"],
                    "title": listing.get("title", ""),
                    "prize": listing.get("prize", ""),
                    "url": listing.get("url", ""),
                    "closing_date": listing.get("closing_date"),
                    "entry_method": listing.get("entry_method"),
                    "requires_purchase": listing.get("requires_purchase", False),
                    "status": "discovered",
                }
            )

    return _json_content({"count": len(listings), "listings": listings})


MOCK_ENTRY_PAGES = {
    "mock://spa-break": (
        "<html><head><title>Win a Weekend Spa Break</title></head>"
        "<body><h1>Enter now</h1><p>No purchase necessary. "
        "Answer: what colour is the sky?</p></body></html>"
    ),
    "mock://coffee-giveaway": (
        "<html><head><title>Coffee Giveaway</title></head>"
        "<body><p>Follow, like, and retweet to enter.</p></body></html>"
    ),
}


def _handle_parse_entry_page(arguments: dict) -> list[TextContent]:
    url = arguments["url"]
    include_html = arguments.get("include_html", False)

    if url.startswith("mock://"):
        html = MOCK_ENTRY_PAGES.get(url)
        if html is None:
            return _json_content({"url": url, "error": f"No mock fixture for {url}"})
        status_code = 200
        content_type = "text/html"
    else:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; prize-draw-mcp-server/1.0)"}
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        html = response.text
        status_code = response.status_code
        content_type = response.headers.get("Content-Type", "")

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    title = soup.title.string if soup.title else ""
    text = soup.get_text(separator="\n", strip=True)
    cleaned_text = "\n".join(line.strip() for line in text.split("\n") if line.strip())

    result = {
        "url": url,
        "status_code": status_code,
        "content_type": content_type,
        "title": title,
        "content": cleaned_text,
        "content_length": len(cleaned_text),
    }
    if include_html:
        result["html"] = html
    return _json_content(result)


def _perform_entry_submission(entry_method: str, arguments: dict, fields: dict) -> dict:
    """Dispatch a non-dry-run submission to the right entry mechanism."""
    if entry_method == "web_form":
        url = arguments.get("url")
        if not url:
            raise ValueError("url is required for entry_method=web_form")
        return entry_mod.submit_web_form(url, fields)

    if entry_method == "email":
        smtp_host = os.environ.get("SMTP_HOST")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER")
        smtp_password = os.environ.get("SMTP_PASSWORD")
        email_to = arguments.get("email_to")
        if not all([smtp_host, smtp_user, smtp_password, email_to]):
            raise ValueError(
                "SMTP_HOST/SMTP_USER/SMTP_PASSWORD env vars and email_to "
                "are required for entry_method=email"
            )
        return entry_mod.submit_email(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_user=smtp_user,
            smtp_password=smtp_password,
            to_addr=email_to,
            subject=arguments.get("email_subject", "Prize draw entry"),
            body=arguments.get("email_body", ""),
        )

    # social
    social_action = arguments.get("social_action")
    if not social_action:
        raise ValueError("social_action is required for entry_method=social")
    return entry_mod.submit_social(social_action, arguments.get("url", ""), fields)


def _handle_submit_entry(arguments: dict) -> list[TextContent]:
    draw_id = arguments["draw_id"]
    entry_method = arguments["entry_method"]
    if entry_method not in entry_mod.VALID_ENTRY_METHODS:
        return _json_content({"error": f"Unknown entry_method: {entry_method!r}"})

    fields = arguments.get("fields", {})
    dry_run = arguments.get("dry_run", True)
    requires_purchase = arguments.get("requires_purchase", False)
    confirm_purchase_required = arguments.get("confirm_purchase_required", False)
    confirm_personal_data = arguments.get("confirm_personal_data", False)
    source = arguments.get("source", "unknown")

    store = get_store()
    existing = store.get(draw_id)
    if existing:
        requires_purchase = existing.get("requires_purchase", requires_purchase)
        source = existing.get("source", source)
    if store.has_entered(draw_id):
        return _json_content(
            {
                "draw_id": draw_id,
                "status": "skipped",
                "reason": "Draw already logged as entered; refusing duplicate entry.",
            }
        )

    try:
        entry_mod.guard_submission(
            requires_purchase=requires_purchase,
            confirm_purchase_required=confirm_purchase_required,
            fields=fields,
            confirm_personal_data=confirm_personal_data,
        )
    except entry_mod.EntryRejected as exc:
        store.upsert(
            {
                "draw_id": draw_id,
                "source": source,
                "entry_method": entry_method,
                "requires_purchase": requires_purchase,
                "status": "failed",
                "notes": str(exc),
            }
        )
        return _json_content(
            {"draw_id": draw_id, "status": "failed", "reason": str(exc)}
        )

    if dry_run:
        preview = {
            "draw_id": draw_id,
            "entry_method": entry_method,
            "fields": fields,
            "would_submit": True,
        }
        store.upsert(
            {
                "draw_id": draw_id,
                "source": source,
                "entry_method": entry_method,
                "requires_purchase": requires_purchase,
                "status": "dry_run",
                "notes": f"Dry run preview: {json.dumps(fields)}",
            }
        )
        return _json_content(
            {"draw_id": draw_id, "status": "dry_run", "preview": preview}
        )

    try:
        result = _perform_entry_submission(entry_method, arguments, fields)
    except Exception as exc:  # noqa: BLE001 - surface any submission failure to the log
        store.upsert(
            {
                "draw_id": draw_id,
                "source": source,
                "entry_method": entry_method,
                "requires_purchase": requires_purchase,
                "status": "failed",
                "notes": str(exc),
            }
        )
        return _json_content(
            {"draw_id": draw_id, "status": "failed", "reason": str(exc)}
        )

    store.upsert(
        {
            "draw_id": draw_id,
            "source": source,
            "entry_method": entry_method,
            "requires_purchase": requires_purchase,
            "status": "entered",
            "entered_at": utcnow_iso(),
            "notes": json.dumps(result),
        }
    )
    return _json_content({"draw_id": draw_id, "status": "entered", "result": result})


def _handle_check_log(arguments: dict) -> list[TextContent]:
    action = arguments["action"]
    store = get_store()

    if action == "list":
        return _json_content({"draws": store.list(status=arguments.get("status"))})

    draw_id = arguments.get("draw_id")
    if action in {"get", "has_seen", "has_entered"} and not draw_id:
        return _json_content({"error": f"draw_id is required for action={action!r}"})

    if action == "get":
        return _json_content({"draw_id": draw_id, "record": store.get(draw_id)})
    if action == "has_seen":
        return _json_content({"draw_id": draw_id, "has_seen": store.has_seen(draw_id)})
    if action == "has_entered":
        return _json_content(
            {"draw_id": draw_id, "has_entered": store.has_entered(draw_id)}
        )
    if action == "record":
        record = dict(arguments.get("record") or {})
        if draw_id:
            record.setdefault("draw_id", draw_id)
        if "draw_id" not in record:
            return _json_content(
                {"error": "record (or draw_id) must include 'draw_id'"}
            )
        record.setdefault("source", "unknown")
        if arguments.get("status"):
            record["status"] = arguments["status"]
        stored = store.upsert(record)
        return _json_content({"draw_id": stored["draw_id"], "record": stored})

    return _json_content({"error": f"Unknown action: {action!r}"})


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    arguments = arguments or {}
    try:
        if name == "search_draws":
            return _handle_search_draws(arguments)
        if name == "parse_entry_page":
            return _handle_parse_entry_page(arguments)
        if name == "submit_entry":
            return _handle_submit_entry(arguments)
        if name == "check_log":
            return _handle_check_log(arguments)
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except requests.exceptions.Timeout:
        return [TextContent(type="text", text="Error: Request timed out")]
    except requests.exceptions.HTTPError as exc:
        return [
            TextContent(
                type="text", text=f"HTTP error: {exc.response.status_code} - {str(exc)}"
            )
        ]
    except (KeyError, ValueError) as exc:
        return [TextContent(type="text", text=f"Invalid arguments: {str(exc)}")]
    except (
        Exception
    ) as exc:  # noqa: BLE001 - last-resort guard so the server keeps running
        return [TextContent(type="text", text=f"Error: {str(exc)}")]


async def main() -> None:
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
