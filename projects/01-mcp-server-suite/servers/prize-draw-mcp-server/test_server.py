#!/usr/bin/env python3
"""
Pytest suite for the prize draw MCP server.

All network calls are mocked - no test hits a real website.
"""

import asyncio
import json

import pytest
import requests

import entry as entry_mod
import server
import sources as sources_mod
from store import PrizeDrawStore


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    """Point every test at a fresh, temp-file-backed store."""
    store_path = tmp_path / "draws.jsonl"
    store = PrizeDrawStore(store_path)
    server.set_store(store)
    yield store
    server.set_store(None)


def call(name: str, arguments: dict) -> dict:
    """Call an MCP tool handler and parse its single JSON TextContent reply."""
    result = asyncio.run(server.call_tool(name, arguments))
    assert len(result) == 1
    return json.loads(result[0].text)


# ---------------------------------------------------------------------------
# search_draws
# ---------------------------------------------------------------------------


def test_search_draws_static_source_returns_mock_listings():
    payload = call("search_draws", {"sources": ["mock-aggregator"]})
    assert payload["count"] == len(sources_mod.MOCK_AGGREGATOR_LISTINGS)
    titles = {listing["title"] for listing in payload["listings"]}
    assert "Win a Weekend Spa Break for Two" in titles


def test_search_draws_respects_limit():
    payload = call("search_draws", {"sources": ["mock-aggregator"], "limit": 1})
    assert payload["count"] == 1
    assert len(payload["listings"]) == 1


def test_search_draws_records_discovered_entries_in_log(isolated_store):
    call("search_draws", {"sources": ["mock-aggregator"]})
    logged = isolated_store.list(status="discovered")
    assert len(logged) == len(sources_mod.MOCK_AGGREGATOR_LISTINGS)


def test_search_draws_rss_source_is_mocked(monkeypatch):
    sample_feed = """<?xml version="1.0"?>
    <rss><channel>
      <item>
        <title>Win a Bike</title>
        <link>https://example-competitions.test/bike</link>
        <description>Free draw, no purchase necessary.</description>
        <pubDate>Mon, 01 Jan 2026 00:00:00 GMT</pubDate>
      </item>
    </channel></rss>
    """

    class FakeResponse:
        text = sample_feed
        status_code = 200

        def raise_for_status(self):
            return None

    def fake_get(url, timeout):
        assert url == "https://example-competitions.test/feed.xml"
        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    payload = call("search_draws", {"sources": ["example-rss"]})
    assert payload["count"] == 1
    assert payload["listings"][0]["title"] == "Win a Bike"


# ---------------------------------------------------------------------------
# parse_entry_page
# ---------------------------------------------------------------------------


def test_parse_entry_page_mock_url_needs_no_network():
    payload = call("parse_entry_page", {"url": "mock://spa-break"})
    assert payload["status_code"] == 200
    assert "Enter now" in payload["content"]
    assert "html" not in payload


def test_parse_entry_page_unknown_mock_url_returns_error():
    payload = call("parse_entry_page", {"url": "mock://does-not-exist"})
    assert "error" in payload


def test_parse_entry_page_fetches_and_strips_scripts(monkeypatch):
    html = (
        "<html><head><title>Real Draw</title></head><body>"
        "<script>evil()</script><p>Enter here</p></body></html>"
    )

    class FakeResponse:
        text = html
        status_code = 200
        headers = {"Content-Type": "text/html"}

        def raise_for_status(self):
            return None

    def fake_get(url, headers, timeout):
        assert url == "https://example-competitions.test/spa-break"
        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    payload = call(
        "parse_entry_page", {"url": "https://example-competitions.test/spa-break"}
    )
    assert payload["title"] == "Real Draw"
    assert "evil()" not in payload["content"]
    assert "Enter here" in payload["content"]


def test_parse_entry_page_include_html(monkeypatch):
    class FakeResponse:
        text = "<html><body>hi</body></html>"
        status_code = 200
        headers = {"Content-Type": "text/html"}

        def raise_for_status(self):
            return None

    monkeypatch.setattr(requests, "get", lambda url, headers, timeout: FakeResponse())

    payload = call(
        "parse_entry_page",
        {"url": "https://example-competitions.test/x", "include_html": True},
    )
    assert payload["html"] == "<html><body>hi</body></html>"


# ---------------------------------------------------------------------------
# submit_entry
# ---------------------------------------------------------------------------


def test_submit_entry_dry_run_does_not_hit_network(monkeypatch):
    def fail_post(*args, **kwargs):
        raise AssertionError("dry_run must not perform a real submission")

    monkeypatch.setattr(requests, "post", fail_post)

    payload = call(
        "submit_entry",
        {
            "draw_id": "mock-aggregator-abc123",
            "entry_method": "web_form",
            "fields": {"answer": "blue"},
            "url": "https://example-competitions.test/spa-break",
            "dry_run": True,
        },
    )
    assert payload["status"] == "dry_run"
    assert payload["preview"]["fields"] == {"answer": "blue"}


def test_submit_entry_web_form_success(monkeypatch, isolated_store):
    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

    def fake_post(url, data, timeout):
        assert url == "https://example-competitions.test/spa-break"
        assert data == {"answer": "blue"}
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    payload = call(
        "submit_entry",
        {
            "draw_id": "draw-1",
            "entry_method": "web_form",
            "fields": {"answer": "blue"},
            "url": "https://example-competitions.test/spa-break",
            "dry_run": False,
        },
    )
    assert payload["status"] == "entered"
    assert isolated_store.has_entered("draw-1")


def test_submit_entry_refuses_personal_data_without_confirmation():
    payload = call(
        "submit_entry",
        {
            "draw_id": "draw-2",
            "entry_method": "web_form",
            "fields": {"email": "person@example.com"},
            "url": "https://example-competitions.test/x",
            "dry_run": False,
        },
    )
    assert payload["status"] == "failed"
    assert "personal" in payload["reason"].lower()


def test_submit_entry_allows_personal_data_with_confirmation(monkeypatch):
    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

    monkeypatch.setattr(requests, "post", lambda url, data, timeout: FakeResponse())

    payload = call(
        "submit_entry",
        {
            "draw_id": "draw-3",
            "entry_method": "web_form",
            "fields": {"email": "person@example.com"},
            "url": "https://example-competitions.test/x",
            "dry_run": False,
            "confirm_personal_data": True,
        },
    )
    assert payload["status"] == "entered"


def test_submit_entry_refuses_purchase_required_without_override():
    payload = call(
        "submit_entry",
        {
            "draw_id": "draw-4",
            "entry_method": "web_form",
            "fields": {"answer": "blue"},
            "url": "https://example-competitions.test/x",
            "dry_run": False,
            "requires_purchase": True,
        },
    )
    assert payload["status"] == "failed"
    assert "purchase" in payload["reason"].lower()


def test_submit_entry_allows_purchase_required_with_override(monkeypatch):
    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

    monkeypatch.setattr(requests, "post", lambda url, data, timeout: FakeResponse())

    payload = call(
        "submit_entry",
        {
            "draw_id": "draw-5",
            "entry_method": "web_form",
            "fields": {"answer": "blue"},
            "url": "https://example-competitions.test/x",
            "dry_run": False,
            "requires_purchase": True,
            "confirm_purchase_required": True,
        },
    )
    assert payload["status"] == "entered"


def test_submit_entry_refuses_duplicate_entry(isolated_store):
    isolated_store.upsert(
        {
            "draw_id": "draw-6",
            "source": "mock-aggregator",
            "status": "entered",
            "entered_at": "2026-01-01T00:00:00+00:00",
        }
    )
    payload = call(
        "submit_entry",
        {
            "draw_id": "draw-6",
            "entry_method": "web_form",
            "fields": {"answer": "blue"},
            "url": "https://example-competitions.test/x",
            "dry_run": False,
        },
    )
    assert payload["status"] == "skipped"
    assert "already logged as entered" in payload["reason"]


def test_submit_entry_uses_stored_requires_purchase_flag(isolated_store):
    isolated_store.upsert(
        {
            "draw_id": "draw-7",
            "source": "mock-aggregator",
            "status": "discovered",
            "requires_purchase": True,
        }
    )
    payload = call(
        "submit_entry",
        {
            "draw_id": "draw-7",
            "entry_method": "web_form",
            "fields": {"answer": "blue"},
            "url": "https://example-competitions.test/x",
            "dry_run": False,
        },
    )
    assert payload["status"] == "failed"
    assert "purchase" in payload["reason"].lower()


def test_submit_entry_social_action_is_simulated_not_live():
    payload = call(
        "submit_entry",
        {
            "draw_id": "draw-8",
            "entry_method": "social",
            "social_action": "follow",
            "url": "https://example.test/profile",
            "dry_run": False,
        },
    )
    assert payload["status"] == "entered"
    assert payload["result"]["simulated"] is True


def test_submit_entry_email_without_smtp_config_fails(monkeypatch):
    for var in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"):
        monkeypatch.delenv(var, raising=False)

    payload = call(
        "submit_entry",
        {
            "draw_id": "draw-9",
            "entry_method": "email",
            "email_to": "competitions@example.test",
            "dry_run": False,
        },
    )
    assert payload["status"] == "failed"


def test_submit_entry_email_success(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "me@example.test")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")

    sent = {}

    class FakeSMTP:
        def __init__(self, host, port):
            sent["host"] = host
            sent["port"] = port

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def starttls(self):
            sent["starttls"] = True

        def login(self, user, password):
            sent["login"] = (user, password)

        def send_message(self, message):
            sent["subject"] = message["Subject"]

    monkeypatch.setattr(entry_mod, "submit_email", entry_mod.submit_email)
    monkeypatch.setattr(entry_mod.smtplib, "SMTP", FakeSMTP)

    payload = call(
        "submit_entry",
        {
            "draw_id": "draw-10",
            "entry_method": "email",
            "email_to": "competitions@example.test",
            "email_subject": "Enter me",
            "dry_run": False,
        },
    )
    assert payload["status"] == "entered"
    assert sent["login"] == ("me@example.test", "secret")
    assert sent["subject"] == "Enter me"


# ---------------------------------------------------------------------------
# check_log
# ---------------------------------------------------------------------------


def test_check_log_record_and_get(isolated_store):
    call(
        "check_log",
        {
            "action": "record",
            "draw_id": "draw-11",
            "record": {"source": "mock-aggregator", "title": "Test Draw"},
        },
    )
    payload = call("check_log", {"action": "get", "draw_id": "draw-11"})
    assert payload["record"]["title"] == "Test Draw"


def test_check_log_has_seen_and_has_entered():
    call(
        "check_log",
        {"action": "record", "draw_id": "draw-12", "record": {"source": "x"}},
    )
    seen = call("check_log", {"action": "has_seen", "draw_id": "draw-12"})
    entered = call("check_log", {"action": "has_entered", "draw_id": "draw-12"})
    assert seen["has_seen"] is True
    assert entered["has_entered"] is False


def test_check_log_list_filters_by_status(isolated_store):
    isolated_store.upsert({"draw_id": "a", "source": "s", "status": "discovered"})
    isolated_store.upsert({"draw_id": "b", "source": "s", "status": "entered"})
    payload = call("check_log", {"action": "list", "status": "entered"})
    assert [d["draw_id"] for d in payload["draws"]] == ["b"]


def test_check_log_unknown_action_returns_error():
    payload = call("check_log", {"action": "bogus"})
    assert "error" in payload


# ---------------------------------------------------------------------------
# entry.guard_submission unit tests
# ---------------------------------------------------------------------------


def test_find_personal_fields_flags_common_markers():
    flagged = entry_mod.find_personal_fields(
        {"answer": "blue", "email": "a@b.com", "card_number": "1234"}
    )
    assert set(flagged) == {"email", "card_number"}


def test_guard_submission_raises_for_purchase_and_personal_data_together():
    with pytest.raises(entry_mod.EntryRejected) as exc_info:
        entry_mod.guard_submission(
            requires_purchase=True,
            confirm_purchase_required=False,
            fields={"email": "a@b.com"},
            confirm_personal_data=False,
        )
    message = str(exc_info.value)
    assert "purchase" in message.lower()
    assert "personal" in message.lower()
