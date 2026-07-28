#!/usr/bin/env python3
"""
Pluggable source configuration for prize draw discovery.

Real aggregator/RSS URLs need to be scoped per issue #21, so this module
ships two placeholder sources that demonstrate the interface without
depending on any live site:

- ``mock-aggregator``: a ``static`` source returning a fixed example listing,
  useful for demos and tests without any network access at all.
- ``example-rss``: an ``rss`` source that fetches and parses a real RSS/Atom
  feed. Point ``url`` at a real feed to use it; tests mock the HTTP call.

Add new sources by appending to ``SOURCES`` (or by passing a custom list
into ``search_draws``/``poll_sources``) - no other code changes required as
long as the source dict has a ``type`` this module understands.
"""

import hashlib
from typing import Optional
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ElementTree
import requests

import robots as robots_mod

REQUEST_TIMEOUT_SECONDS = 10
USER_AGENT = "Mozilla/5.0 (compatible; prize-draw-mcp-server/1.0)"
RobotsDisallowedError = robots_mod.RobotsDisallowedError

MOCK_AGGREGATOR_LISTINGS = [
    {
        "title": "Win a Weekend Spa Break for Two",
        "url": "https://example-competitions.test/spa-break",
        "prize": "Weekend spa break for two",
        "closing_date": "2026-08-15",
        "entry_method": "web_form",
        "requires_purchase": False,
        "summary": "Free entry, no purchase necessary. Fill in the form to enter.",
    },
    {
        "title": "Win a Year's Supply of Coffee",
        "url": "https://example-competitions.test/coffee-giveaway",
        "prize": "Year's supply of coffee",
        "closing_date": "2026-09-01",
        "entry_method": "social",
        "requires_purchase": False,
        "summary": "Follow, like, and retweet the announcement post to enter.",
    },
]

# Pluggable source registry. Real URLs are intentionally left as
# placeholders (issue #21 scopes actual source selection).
SOURCES = [
    {
        "name": "mock-aggregator",
        "type": "static",
        "listings": MOCK_AGGREGATOR_LISTINGS,
    },
    {
        "name": "example-rss",
        "type": "rss",
        "url": "https://example-competitions.test/feed.xml",
    },
]


def make_draw_id(source_name: str, url: str) -> str:
    """Derive a stable draw id from a source name and entry URL.

    This is an identity fingerprint, not a security control, hence
    usedforsecurity=False.
    """
    digest = hashlib.sha1(
        f"{source_name}:{url}".encode("utf-8"), usedforsecurity=False
    ).hexdigest()[:16]
    return f"{source_name}-{digest}"


def get_source(name: str) -> Optional[dict]:
    """Look up a configured source by name."""
    for source in SOURCES:
        if source["name"] == name:
            return source
    return None


def _poll_static(source: dict) -> list[dict]:
    listings = []
    for item in source["listings"]:
        listing = dict(item)
        listing["source"] = source["name"]
        listing["draw_id"] = make_draw_id(source["name"], listing["url"])
        listings.append(listing)
    return listings


def _rss_text(element: Element, tag: str) -> str:
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _parse_rss(xml_text: str, source_name: str) -> list[dict]:
    """Parse a minimal RSS 2.0 feed into draw listing dicts.

    Only the handful of fields prize-draw entries typically need are
    extracted (title/link/description/pubDate); anything else in the feed
    is ignored. Malformed items are skipped rather than raising, since a
    single bad `<item>` shouldn't take down the whole poll.
    """
    listings = []
    root = ElementTree.fromstring(xml_text)
    for item in root.iter("item"):
        link = _rss_text(item, "link")
        if not link:
            continue
        listings.append(
            {
                "source": source_name,
                "draw_id": make_draw_id(source_name, link),
                "title": _rss_text(item, "title"),
                "url": link,
                "prize": "",
                "closing_date": None,
                "entry_method": None,
                "requires_purchase": False,
                "summary": _rss_text(item, "description"),
                "published": _rss_text(item, "pubDate"),
            }
        )
    return listings


def _poll_rss(source: dict, session: requests.Session) -> list[dict]:
    url = source["url"]
    if not robots_mod.is_allowed(url, USER_AGENT, session=session):
        raise robots_mod.RobotsDisallowedError(
            f"robots.txt disallows fetching {url} for {USER_AGENT!r}"
        )
    response = session.get(
        url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    return _parse_rss(response.text, source["name"])


def poll_source(source: dict, session: Optional[requests.Session] = None) -> list[dict]:
    """Poll a single configured source and return raw draw listings."""
    source_type = source.get("type")
    if source_type == "static":
        return _poll_static(source)
    if source_type == "rss":
        return _poll_rss(source, session or requests)
    raise ValueError(f"Unknown source type: {source_type!r}")


def poll_sources(
    names: Optional[list[str]] = None, session: Optional[requests.Session] = None
) -> list[dict]:
    """Poll every configured source (or a filtered subset by name)."""
    selected = SOURCES if not names else [s for s in SOURCES if s["name"] in names]
    results = []
    for source in selected:
        results.extend(poll_source(source, session=session))
    return results
