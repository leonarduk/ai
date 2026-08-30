"""Snapshot leonarduk's public GitHub repos into knowledge/github.json.

Usage:
    python build/build_github_snapshot.py --user leonarduk --out knowledge/github.json

Baking the snapshot at build time (rather than calling the API mid-conversation)
keeps chat replies fast, avoids rate limits, and means no GitHub token is present
at chat time. See docs/design.md §3.3.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests

GITHUB_API = "https://api.github.com"
KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"
README_EXCERPT_LIMIT = 1200

HEADING_LINE_RE = re.compile(r"^##\s+(\S+)\s*$")

IMAGE_OR_BADGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
HTML_TAG_RE = re.compile(r"<[^>]+>")
HEADING_MARKER_RE = re.compile(r"^#{1,6}\s*", re.MULTILINE)

# Paired emphasis/code delimiters only — a bare "_" or "*" inside an
# identifier (GITHUB_TOKEN, multi_agent_coder) must survive untouched.
BOLD_STAR_RE = re.compile(r"\*\*([^*\n]+)\*\*")
BOLD_UNDERSCORE_RE = re.compile(r"__([^_\n]+)__")
ITALIC_STAR_RE = re.compile(r"\*([^*\n]+)\*")
CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")

BLANK_RUN_RE = re.compile(r"\n{3,}")


class GitHubAPIError(Exception):
    """A GitHub API call failed with a non-recoverable error."""


class GitHubRateLimitError(GitHubAPIError):
    """The GitHub API rate limit was exhausted."""


def _get(url, token, params=None, accept="application/vnd.github+json"):
    headers = {"Accept": accept}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.get(url, headers=headers, params=params, timeout=15)

    if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
        raise GitHubRateLimitError(f"GitHub API rate limit exceeded fetching {url}")
    if response.status_code >= 400 and response.status_code != 404:
        raise GitHubAPIError(f"GitHub API error {response.status_code} fetching {url}")

    return response


def fetch_repos(user, token=None):
    """Return public, non-fork, non-archived repos owned by `user`."""
    repos = []
    page = 1
    while True:
        response = _get(
            f"{GITHUB_API}/users/{user}/repos",
            token,
            params={"type": "owner", "per_page": 100, "page": page},
        )
        batch = response.json()
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    return [
        repo
        for repo in repos
        if not repo.get("fork") and not repo.get("archived") and not repo.get("private")
    ]


def fetch_languages(owner, name, token=None):
    """Return the repo's languages, most-used first, ties broken alphabetically."""
    response = _get(f"{GITHUB_API}/repos/{owner}/{name}/languages", token)
    if response.status_code != 200:
        return []
    data = response.json()
    return sorted(data.keys(), key=lambda lang: (-data[lang], lang))


def fetch_readme(owner, name, token=None):
    """Return the repo's README as raw text, or "" if it has none."""
    response = _get(
        f"{GITHUB_API}/repos/{owner}/{name}/readme",
        token,
        accept="application/vnd.github.raw",
    )
    if response.status_code == 404:
        return ""
    return response.text


def strip_markdown(text):
    """Remove badges, images, links, headings and emphasis markup from README text.

    Only paired emphasis/code delimiters are stripped — a bare "_" or "*"
    inside an identifier (GITHUB_TOKEN, multi_agent_coder) is left alone,
    since there's no reliable way to tell it apart from real emphasis syntax.
    """
    text = IMAGE_OR_BADGE_RE.sub("", text)
    text = LINK_RE.sub(r"\1", text)
    text = HTML_TAG_RE.sub("", text)
    text = HEADING_MARKER_RE.sub("", text)
    text = BOLD_STAR_RE.sub(r"\1", text)
    text = BOLD_UNDERSCORE_RE.sub(r"\1", text)
    text = ITALIC_STAR_RE.sub(r"\1", text)
    text = CODE_SPAN_RE.sub(r"\1", text)
    text = BLANK_RUN_RE.sub("\n\n", text)
    return text.strip()


def readme_excerpt(readme_text, limit=README_EXCERPT_LIMIT):
    return strip_markdown(readme_text)[:limit]


def parse_projects_md(path):
    """Parse `## repo-name` sections into {repo_name: note_text}."""
    if not path.exists():
        return {}

    notes = {}
    current_name = None
    buffer = []

    def flush():
        if current_name is not None:
            notes[current_name] = "\n".join(buffer).strip()

    for line in path.read_text(encoding="utf-8").splitlines():
        match = HEADING_LINE_RE.match(line)
        if match:
            flush()
            current_name = match.group(1)
            buffer = []
        else:
            buffer.append(line)
    flush()

    return notes


def build_snapshot(user, token=None, projects_md_path=None):
    """Fetch and assemble one record per repo, sorted deterministically by name."""
    if projects_md_path is None:
        projects_md_path = KNOWLEDGE_DIR / "projects.md"
    curated_notes = parse_projects_md(projects_md_path)

    records = []
    for repo in fetch_repos(user, token):
        owner = repo["owner"]["login"]
        name = repo["name"]
        readme_text = fetch_readme(owner, name, token)

        records.append(
            {
                "name": name,
                "description": repo.get("description") or "",
                "url": repo["html_url"],
                "topics": sorted(repo.get("topics") or []),
                "languages": fetch_languages(owner, name, token),
                "stars": repo.get("stargazers_count", 0),
                "pushed_at": (repo.get("pushed_at") or "")[:10],
                "readme_excerpt": readme_excerpt(readme_text),
                "curated_note": curated_notes.get(name),
            }
        )

    records.sort(key=lambda record: record["name"])
    return records


def write_snapshot(records, out_path):
    out_path.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", default="leonarduk")
    parser.add_argument("--out", default=str(KNOWLEDGE_DIR / "github.json"))
    args = parser.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN")

    try:
        records = build_snapshot(args.user, token)
    except GitHubAPIError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    write_snapshot(records, Path(args.out))
    print(f"Wrote {len(records)} repos to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
