#!/usr/bin/env python3
"""
robots.txt compliance check for outbound scraping requests.

``search_draws`` (via ``sources.py``'s RSS polling) and ``parse_entry_page``
must not fetch a URL a site's robots.txt disallows for our user agent. This
module fetches and caches each domain's robots.txt (per process) and answers
"is this URL allowed?" via the standard library's ``urllib.robotparser``.

A site with no robots.txt, or one that fails to fetch (network error,
non-200 status), is treated as allowing everything - that matches how
robots.txt is specified to behave (absence of a rule permits access) and
avoids a transient fetch failure silently blocking scraping.
"""

from typing import Optional
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests

ROBOTS_REQUEST_TIMEOUT_SECONDS = 10


class RobotsDisallowedError(Exception):
    """Raised when a URL's robots.txt disallows fetching it for our agent."""


# Per-process cache of RobotFileParser instances, keyed by scheme+netloc.
_robots_cache: dict[str, RobotFileParser] = {}


def _robots_txt_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))


def _fetch_robots_parser(
    url: str, session: Optional[requests.Session] = None
) -> RobotFileParser:
    parser = RobotFileParser()
    robots_url = _robots_txt_url(url)
    parser.set_url(robots_url)
    try:
        response = (session or requests).get(
            robots_url, timeout=ROBOTS_REQUEST_TIMEOUT_SECONDS
        )
        if response.status_code >= 400:
            parser.parse([])
        else:
            parser.parse(response.text.splitlines())
    except requests.exceptions.RequestException:
        # Fetch failed - default to allow, per robots.txt semantics for a
        # missing file, rather than blocking scraping on a transient error.
        parser.parse([])
    return parser


def is_allowed(
    url: str,
    user_agent: str,
    session: Optional[requests.Session] = None,
    cache: Optional[dict[str, RobotFileParser]] = None,
) -> bool:
    """Return whether ``user_agent`` may fetch ``url`` per its robots.txt."""
    if cache is None:
        cache = _robots_cache
    parts = urlsplit(url)
    cache_key = f"{parts.scheme}://{parts.netloc}"
    parser = cache.get(cache_key)
    if parser is None:
        parser = _fetch_robots_parser(url, session=session)
        cache[cache_key] = parser
    return parser.can_fetch(user_agent, url)


def clear_cache() -> None:
    """Clear the module-level robots.txt cache (used by tests)."""
    _robots_cache.clear()
