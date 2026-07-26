import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from ollama_classifier import OllamaConnectionError, _parse_labels, classify_email


class TestParseLabels:
    def test_exact_match(self):
        assert _parse_labels('{"labels": ["Work"]}', ["Work", "Personal"]) == ["Work"]

    def test_case_insensitive_match_returns_canonical_name(self):
        assert _parse_labels('{"labels": ["work"]}', ["Work", "Personal"]) == ["Work"]

    def test_multiple_labels(self):
        result = _parse_labels(
            '{"labels": ["Work", "Urgent"]}', ["Work", "Urgent", "Personal"]
        )
        assert result == ["Work", "Urgent"]

    def test_unknown_label_is_dropped(self):
        assert _parse_labels('{"labels": ["Spam"]}', ["Work", "Personal"]) == []

    def test_empty_array_means_no_label(self):
        assert _parse_labels('{"labels": []}', ["Work"]) == []

    def test_malformed_json_returns_empty(self):
        assert _parse_labels("not json", ["Work"]) == []

    def test_bare_array_without_wrapper_object_returns_empty(self):
        assert _parse_labels('["Work"]', ["Work"]) == []

    def test_missing_labels_key_returns_empty(self):
        assert _parse_labels('{"other": "Work"}', ["Work"]) == []

    def test_duplicates_are_deduped(self):
        assert _parse_labels('{"labels": ["Work", "work"]}', ["Work"]) == ["Work"]


class TestClassifyEmail:
    def test_no_labels_available_returns_empty_without_network_call(self):
        with patch("ollama_classifier.requests.post") as mock_post:
            result = classify_email("Subj", "a@b.com", "snippet", labels=[])
        assert result == []
        mock_post.assert_not_called()

    def test_calls_local_ollama_and_parses_response(self):
        mock_response = Mock()
        mock_response.json.return_value = {"response": '{"labels": ["Work"]}'}
        mock_response.raise_for_status = Mock()

        with patch("ollama_classifier.requests.post", return_value=mock_response) as mock_post:
            result = classify_email(
                "Meeting notes",
                "boss@company.com",
                "Let's sync tomorrow",
                labels=["Work", "Personal"],
                model="llama3",
                host="http://localhost:11434",
            )

        assert result == ["Work"]
        called_url = mock_post.call_args.args[0]
        assert called_url == "http://localhost:11434/api/generate"
        payload = mock_post.call_args.kwargs["json"]
        assert payload["model"] == "llama3"
        assert "Work" in payload["prompt"]
        assert "Personal" in payload["prompt"]
        # format must be a JSON schema constraining to {"labels": [...]},
        # not the bare "json" string - that only forces *some* JSON object
        # back (e.g. {"Work": true}), not this shape.
        assert payload["format"]["properties"]["labels"]["items"]["enum"] == [
            "Work",
            "Personal",
        ]

    def test_connection_error_raises_ollama_connection_error(self):
        with patch(
            "ollama_classifier.requests.post",
            side_effect=requests.exceptions.ConnectionError(),
        ):
            with pytest.raises(OllamaConnectionError):
                classify_email("Subj", "a@b.com", "snippet", labels=["Work"])

    def test_strips_trailing_slash_from_host(self):
        mock_response = Mock()
        mock_response.json.return_value = {"response": '{"labels": []}'}
        mock_response.raise_for_status = Mock()

        with patch("ollama_classifier.requests.post", return_value=mock_response) as mock_post:
            classify_email(
                "Subj", "a@b.com", "snippet", labels=["Work"], host="http://localhost:11434/"
            )

        assert mock_post.call_args.args[0] == "http://localhost:11434/api/generate"
