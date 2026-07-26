"""Unit tests for extract_followups.py."""

from __future__ import annotations

import sys
from pathlib import Path

# Add the scripts directory to the Python path so we can import extract_followups
sys.path.insert(0, str(Path(__file__).parent))

from extract_followups import extract_followups


class TestExtractFollowups:
    """Test extraction of follow-up issue titles from review section 5."""

    def test_no_section_returns_empty_list(self) -> None:
        """A review with no section 5 heading yields no follow-ups."""
        review_text = """
## Review

### 1. Acceptance criteria
All good.

**APPROVE**
"""
        assert extract_followups(review_text) == []

    def test_extracts_dash_bullets(self) -> None:
        """Dash-bulleted titles under section 5 are extracted in order."""
        review_text = """
### 5. Suggested follow-up issues (optional)
- Add tests for `truncate_diff`
- Broaden the `Closes #` regex

**APPROVE**
"""
        assert extract_followups(review_text) == [
            "Add tests for `truncate_diff`",
            "Broaden the `Closes #` regex",
        ]

    def test_extracts_star_bullets(self) -> None:
        """Star-bulleted titles are also recognized."""
        review_text = """
## 5. Suggested follow-up issues
* Document the `Deep Review Required` label
* Add a `docs/AI_REVIEW_WORKFLOWS.md`

**REQUEST CHANGES** — see above
"""
        assert extract_followups(review_text) == [
            "Document the `Deep Review Required` label",
            "Add a `docs/AI_REVIEW_WORKFLOWS.md`",
        ]

    def test_stops_at_next_heading(self) -> None:
        """Bullets after a following heading are not included."""
        review_text = """
### 5. Suggested follow-up issues (optional)
- Add tests for `extract_followups`

### 6. Not a real section
- This should not be picked up
"""
        assert extract_followups(review_text) == ["Add tests for `extract_followups`"]

    def test_stops_at_verdict_line(self) -> None:
        """Bullets are not picked up past an inline verdict line."""
        review_text = """
### 5. Suggested follow-up issues (optional)
- Add tests for `truncate_diff`

**APPROVE** — no blocking concerns
- Not a real follow-up, just prose after the verdict
"""
        assert extract_followups(review_text) == ["Add tests for `truncate_diff`"]

    def test_verdict_line_itself_not_treated_as_bullet(self) -> None:
        """A verdict rendered as a bulleted line is excluded from the titles."""
        review_text = """
### 5. Suggested follow-up issues (optional)
- Add tests for `truncate_diff`
- **APPROVE**
"""
        assert extract_followups(review_text) == ["Add tests for `truncate_diff`"]

    def test_low_specificity_titles_without_reference_are_dropped(self) -> None:
        """Generic phrasing with no backtick-quoted reference is filtered out."""
        review_text = """
### 5. Suggested follow-up issues (optional)
- Consider adding more detailed comments for clarity
- Improve readability
- Add tests for `extract_followups`
"""
        assert extract_followups(review_text) == ["Add tests for `extract_followups`"]

    def test_low_specificity_phrasing_kept_when_it_has_a_reference(self) -> None:
        """Generic-sounding phrasing is kept if it names a concrete reference."""
        review_text = """
### 5. Suggested follow-up issues (optional)
- Consider adding more detailed comments for clarity in `review_common.py`
"""
        assert extract_followups(review_text) == [
            "Consider adding more detailed comments for clarity in `review_common.py`"
        ]

    def test_bare_bullet_marker_merges_into_next_line(self) -> None:
        """Documents current behavior for a bare `-` bullet with no same-line text.

        `\\s+` in the bullet regex is greedy and matches across the newline, so a
        marker with nothing after it on its own line doesn't get skipped as an
        empty title (there's no input that reaches the `if not title` guard with
        the current pattern) — instead it merges into the following line's text.
        This isn't the behavior you'd expect from the guard's intent, but it's
        what the shipped regex actually does; pinning it here so a future change
        to the pattern shows up as an intentional test update, not a silent
        behavior change.
        """
        review_text = """
### 5. Suggested follow-up issues (optional)
-
- Add tests for `truncate_diff`
"""
        assert extract_followups(review_text) == ["- Add tests for `truncate_diff`"]
