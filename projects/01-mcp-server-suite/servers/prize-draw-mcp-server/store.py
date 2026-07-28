#!/usr/bin/env python3
"""
Data store for the prize draw MCP server.

Tracks discovered/entered prize draws in a simple append-only JSONL file so
that ``check_log`` can answer "have we seen/entered this draw before?"
without any external database dependency.

Schema (one JSON object per line)::

    {
        "draw_id":            str   - stable identifier for the draw
        "source":             str   - name of the source that produced it
        "title":              str   - human readable title
        "prize":              str   - prize description
        "url":                str   - entry page / feed item URL
        "closing_date":       str | None - ISO-8601 date the draw closes
        "entry_method":       str | None - "web_form" | "email" | "social"
        "requires_purchase":  bool  - whether entry requires a purchase
        "status":             str   - "discovered" | "dry_run" | "entered"
                                        | "skipped" | "failed"
        "entered_at":         str | None - ISO-8601 timestamp of entry
        "notes":              str   - free-form notes/result details
        "updated_at":         str   - ISO-8601 timestamp of this record
    }

The file is append-only: each call to :meth:`PrizeDrawStore.upsert` appends a
new line rather than mutating existing ones, so the file doubles as a full
audit trail. Readers (``get``/``list``/``has_seen``/``has_entered``) always
resolve to the *latest* line for a given ``draw_id``.
"""

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_STORE_PATH = Path(__file__).parent / "data" / "draws.jsonl"

VALID_STATUSES = {"discovered", "dry_run", "entered", "skipped", "failed"}


def utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DrawRecord:
    """A single row of the prize draw data store."""

    draw_id: str
    source: str
    title: str = ""
    prize: str = ""
    url: str = ""
    closing_date: Optional[str] = None
    entry_method: Optional[str] = None
    requires_purchase: bool = False
    status: str = "discovered"
    entered_at: Optional[str] = None
    notes: str = ""
    updated_at: str = field(default_factory=utcnow_iso)

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status {self.status!r}; must be one of {sorted(VALID_STATUSES)}"
            )

    def to_dict(self) -> dict:
        return asdict(self)


class PrizeDrawStore:
    """JSONL-backed store for discovered/entered prize draws.

    A single writer lock keeps concurrent appends from interleaving; reads
    replay the whole file which is fine at the scale this tool operates at
    (a personal prize-draw log, not a production event store).
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else DEFAULT_STORE_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
        return records

    def _latest_by_id(self) -> dict:
        latest: dict = {}
        for record in self._read_all():
            latest[record["draw_id"]] = record
        return latest

    def get(self, draw_id: str) -> Optional[dict]:
        """Return the latest known record for ``draw_id``, or ``None``."""
        return self._latest_by_id().get(draw_id)

    def has_seen(self, draw_id: str) -> bool:
        """Return whether ``draw_id`` has ever been recorded."""
        return self.get(draw_id) is not None

    def has_entered(self, draw_id: str) -> bool:
        """Return whether ``draw_id`` already has a status of ``entered``."""
        record = self.get(draw_id)
        return bool(record and record.get("status") == "entered")

    def list(self, status: Optional[str] = None) -> list[dict]:
        """List the latest record per draw, optionally filtered by status."""
        records = list(self._latest_by_id().values())
        if status:
            records = [r for r in records if r.get("status") == status]
        return sorted(records, key=lambda r: r.get("updated_at", ""))

    def upsert(self, record: dict) -> dict:
        """Append a new (or updated) record for a draw.

        ``record`` must at minimum contain ``draw_id`` and ``source``.
        Returns the stored record (with ``updated_at`` filled in if absent).
        """
        if "draw_id" not in record:
            raise ValueError("record must include 'draw_id'")
        stored = dict(record)
        stored.setdefault("updated_at", utcnow_iso())
        stored.setdefault("status", "discovered")
        if stored["status"] not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status {stored['status']!r}; must be one of {sorted(VALID_STATUSES)}"
            )
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(stored) + "\n")
        return stored
