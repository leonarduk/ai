"""Tests for avatar/context.py."""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from avatar import context  # noqa: E402


def make_repo(name, pushed_at, readme_len=200, **overrides):
    repo = {
        "name": name,
        "description": f"{name} description",
        "url": f"https://github.com/leonarduk/{name}",
        "topics": ["agents"],
        "languages": ["Python"],
        "stars": 1,
        "pushed_at": pushed_at,
        "readme_excerpt": "x" * readme_len,
        "curated_note": None,
    }
    repo.update(overrides)
    return repo


@pytest.fixture
def knowledge_dir(tmp_path):
    (tmp_path / "summary.txt").write_text(
        "I'm a senior engineer with 20 years of experience.", encoding="utf-8"
    )
    (tmp_path / "profile.md").write_text(
        "## Experience\nSenior Software Engineer at Acme.", encoding="utf-8"
    )
    (tmp_path / "github.json").write_text(
        json.dumps([make_repo("issue-worm", "2026-08-20")]), encoding="utf-8"
    )
    return tmp_path


class TestBuildSystemPrompt:
    def test_deterministic_across_repeated_calls(self, knowledge_dir):
        first = context.build_system_prompt(knowledge_dir=knowledge_dir)
        second = context.build_system_prompt(knowledge_dir=knowledge_dir)
        assert first == second

    def test_includes_role_summary_profile_and_rules(self, knowledge_dir):
        prompt = context.build_system_prompt(knowledge_dir=knowledge_dir)
        assert "AI twin" in prompt
        assert "20 years of experience" in prompt
        assert "Senior Software Engineer at Acme" in prompt
        assert context.RULES_BLOCK_PLACEHOLDER in prompt

    def test_includes_github_index(self, knowledge_dir):
        prompt = context.build_system_prompt(knowledge_dir=knowledge_dir)
        assert "issue-worm" in prompt

    def test_missing_github_json_degrades_to_profile_only(self, tmp_path, caplog):
        (tmp_path / "summary.txt").write_text("Summary text.", encoding="utf-8")
        (tmp_path / "profile.md").write_text("Profile text.", encoding="utf-8")
        # No github.json written.

        with caplog.at_level("WARNING"):
            prompt = context.build_system_prompt(knowledge_dir=tmp_path)

        assert "Summary text." in prompt
        assert "Profile text." in prompt
        assert any(
            "GitHub snapshot missing" in record.message for record in caplog.records
        )

    def test_missing_summary_and_profile_do_not_crash(self, tmp_path):
        (tmp_path / "github.json").write_text(json.dumps([]), encoding="utf-8")
        prompt = context.build_system_prompt(knowledge_dir=tmp_path)
        assert context.ROLE_BLOCK in prompt

    def test_malformed_github_json_structure_degrades_to_profile_only(
        self, tmp_path, caplog
    ):
        (tmp_path / "summary.txt").write_text("Summary text.", encoding="utf-8")
        (tmp_path / "profile.md").write_text("Profile text.", encoding="utf-8")
        # Structurally valid JSON, but a dict instead of the expected list.
        (tmp_path / "github.json").write_text(
            json.dumps({"repos": []}), encoding="utf-8"
        )

        with caplog.at_level("WARNING"):
            prompt = context.build_system_prompt(knowledge_dir=tmp_path)

        assert "Summary text." in prompt
        assert any("not a JSON list" in record.message for record in caplog.records)

    def test_reads_budget_from_env_var(self, knowledge_dir, monkeypatch):
        monkeypatch.setenv("AVATAR_MAX_CONTEXT_TOKENS", "5")

        with pytest.raises(context.PromptTooLargeError) as exc_info:
            context.build_system_prompt(knowledge_dir=knowledge_dir)

        assert "5" in str(exc_info.value)

    def test_explicit_max_tokens_overrides_env_var(self, knowledge_dir, monkeypatch):
        monkeypatch.setenv("AVATAR_MAX_CONTEXT_TOKENS", "5")

        # Should not raise: the explicit argument wins over the env var.
        context.build_system_prompt(max_tokens=40000, knowledge_dir=knowledge_dir)

    def test_no_volatile_timestamp_content(self, knowledge_dir):
        prompt = context.build_system_prompt(knowledge_dir=knowledge_dir)
        # A static pushed_at date (YYYY-MM-DD) is legitimate committed data;
        # a wall-clock timestamp with a time component would not be.
        assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", prompt)

    def test_unfittable_prompt_raises_with_budget_and_size(self, knowledge_dir):
        with pytest.raises(context.PromptTooLargeError) as exc_info:
            context.build_system_prompt(max_tokens=5, knowledge_dir=knowledge_dir)

        message = str(exc_info.value)
        assert "5" in message


class TestGithubSectionTrimming:
    def test_200_repo_snapshot_trims_oldest_first(self, tmp_path):
        (tmp_path / "summary.txt").write_text("Summary.", encoding="utf-8")
        (tmp_path / "profile.md").write_text("Profile.", encoding="utf-8")

        repos = [
            make_repo(
                f"repo-{i:03d}", pushed_at=f"2026-01-{(i % 28) + 1:02d}", readme_len=300
            )
            for i in range(200)
        ]
        (tmp_path / "github.json").write_text(json.dumps(repos), encoding="utf-8")

        prompt = context.build_system_prompt(max_tokens=8000, knowledge_dir=tmp_path)

        # Every repo still appears (as a full record or an index line)...
        for repo in repos:
            assert repo["name"] in prompt
        # ...but not every repo can have kept its full record at this budget.
        full_record_count = prompt.count("### repo-")
        assert 0 < full_record_count < 200

    def test_oldest_pushed_repos_are_demoted_before_newest(self, tmp_path):
        (tmp_path / "summary.txt").write_text("Summary.", encoding="utf-8")
        (tmp_path / "profile.md").write_text("Profile.", encoding="utf-8")

        repos = [
            make_repo("oldest", pushed_at="2020-01-01", readme_len=2000),
            make_repo("newest", pushed_at="2026-08-01", readme_len=2000),
        ]
        (tmp_path / "github.json").write_text(json.dumps(repos), encoding="utf-8")

        # Budget tight enough that only one repo can keep its full record.
        prompt = context.build_system_prompt(max_tokens=900, knowledge_dir=tmp_path)

        assert "### newest" in prompt
        assert "### oldest" not in prompt

    def test_missing_pushed_at_does_not_crash(self, tmp_path):
        (tmp_path / "summary.txt").write_text("Summary.", encoding="utf-8")
        (tmp_path / "profile.md").write_text("Profile.", encoding="utf-8")
        repo = make_repo("no-date", pushed_at="")
        (tmp_path / "github.json").write_text(json.dumps([repo]), encoding="utf-8")

        prompt = context.build_system_prompt(knowledge_dir=tmp_path)

        assert "no-date" in prompt


class TestEstimateTokens:
    def test_scales_with_text_length(self):
        assert context.estimate_tokens("a" * 600) > context.estimate_tokens("a" * 300)


class TestFormatIndexLine:
    def test_handles_missing_description(self):
        record = {"name": "no-desc", "description": None}
        line = context._format_index_line(record)
        assert "no-desc" in line


class TestFormatFullRecord:
    def test_handles_empty_topics_and_languages(self):
        record = {
            "name": "bare",
            "description": "",
            "topics": [],
            "languages": [],
            "stars": 0,
            "curated_note": None,
            "readme_excerpt": "",
        }
        block = context._format_full_record(record)
        assert "### bare" in block
        assert "Topics:" not in block
        assert "Languages:" not in block
