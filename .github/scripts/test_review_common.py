"""Unit tests for review_common.truncate_diff."""

from __future__ import annotations

import sys
from pathlib import Path

# Add the scripts directory to the Python path so we can import review_common
sys.path.insert(0, str(Path(__file__).parent))

from review_common import TRUNCATION_NOTICE_TEMPLATE, truncate_diff


def _make_block(path: str, body_lines: int) -> str:
    """Build a minimal whole-file diff block `split_diff_blocks` will recognize."""
    header = f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
    body = "".join(f"+line {i} of {path}\n" for i in range(body_lines))
    return header + body


class TestTruncateDiff:
    """Test truncate_diff's whole-file-boundary truncation behaviour."""

    def test_under_limit_returned_unchanged(self) -> None:
        """A diff at or under the limit passes through untouched."""
        diff = _make_block("small.py", 5)
        result, was_truncated = truncate_diff(diff, limit=len(diff) + 10)
        assert result == diff
        assert was_truncated is False

    def test_exactly_at_limit_returned_unchanged(self) -> None:
        """A diff exactly the size of the limit is not considered over-budget."""
        diff = _make_block("exact.py", 3)
        result, was_truncated = truncate_diff(diff, limit=len(diff))
        assert result == diff
        assert was_truncated is False

    def test_keeps_whole_blocks_that_fit_and_drops_the_rest(self) -> None:
        """When multiple file blocks overflow the budget, keep whichever whole
        blocks fit and append a notice naming how many were kept/skipped."""
        block_a = _make_block("a.py", 10)
        block_b = _make_block("b.py", 10)
        block_c = _make_block("c.py", 10)
        diff = block_a + block_b + block_c

        # Budget for exactly the first two blocks plus a little slack for the notice.
        limit = len(block_a) + len(block_b) + 200
        result, was_truncated = truncate_diff(diff, limit=limit)

        assert was_truncated is True
        assert "a.py" in result
        assert "b.py" in result
        assert "c.py" not in result
        assert "skipped 1 additional file(s)" in result
        assert len(result) <= limit

    def test_single_oversized_block_hard_truncates_at_line_boundary(self) -> None:
        """When a single file block itself exceeds the limit, fall back to a
        hard truncation of that block cut at the nearest line boundary."""
        diff = _make_block("huge.py", 200)
        limit = 500
        result, was_truncated = truncate_diff(diff, limit=limit)

        assert was_truncated is True
        assert "skipped 1 additional file(s)" in result
        # The kept prefix (before the appended notice) must end on a full line.
        notice_start = result.index("\n\n[diff truncated")
        kept_prefix = result[:notice_start]
        assert diff.startswith(kept_prefix.rstrip("\n") + "\n") or kept_prefix == ""

    def test_result_never_exceeds_limit_even_with_notice_appended(self) -> None:
        """The kept content is re-trimmed if adding the notice would itself
        push the result past the limit."""
        block_a = _make_block("a.py", 10)
        block_b = _make_block("b.py", 10)
        diff = block_a + block_b

        # A tight limit that fits block_a alone but leaves little room for the notice.
        limit = len(block_a) + 20
        result, was_truncated = truncate_diff(diff, limit=limit)

        assert was_truncated is True
        assert len(result) <= limit

    def test_notice_reports_correct_kept_and_skipped_counts(self) -> None:
        """The truncation notice names exactly how many blocks were kept vs skipped."""
        blocks = [_make_block(f"file{i}.py", 5) for i in range(4)]
        diff = "".join(blocks)

        expected_notice = TRUNCATION_NOTICE_TEMPLATE.format(kept_files=2, skipped_files=2)
        # Leave enough headroom for the notice itself so the second (notice-fitting)
        # trim pass doesn't have to cut into the second block's content.
        limit = len(blocks[0]) + len(blocks[1]) + len(expected_notice) + 5
        result, _ = truncate_diff(diff, limit=limit)

        assert expected_notice.strip() in result

    def test_empty_diff_is_not_truncated(self) -> None:
        """An empty diff is trivially under any limit."""
        result, was_truncated = truncate_diff("", limit=100)
        assert result == ""
        assert was_truncated is False
