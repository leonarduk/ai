import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from label_inbox import (
    apply_labels,
    get_message_summary,
    get_user_labels,
    list_inbox_message_ids,
    run,
)


def make_service():
    return MagicMock()


class TestGetUserLabels:
    def test_filters_to_user_labels_only(self):
        service = make_service()
        service.users().labels().list().execute.return_value = {
            "labels": [
                {"id": "l1", "name": "Work", "type": "user"},
                {"id": "INBOX", "name": "INBOX", "type": "system"},
                {"id": "l2", "name": "Personal", "type": "user"},
            ]
        }
        result = get_user_labels(service)
        assert result == {"Work": "l1", "Personal": "l2"}


class TestGetMessageSummary:
    def test_extracts_headers_and_snippet(self):
        service = make_service()
        service.users().messages().get().execute.return_value = {
            "payload": {
                "headers": [
                    {"name": "From", "value": "boss@company.com"},
                    {"name": "Subject", "value": "Meeting"},
                ]
            },
            "snippet": "Let's sync",
        }
        result = get_message_summary(service, "msg1")
        assert result == {
            "id": "msg1",
            "subject": "Meeting",
            "sender": "boss@company.com",
            "snippet": "Let's sync",
        }

    def test_missing_headers_use_defaults(self):
        service = make_service()
        service.users().messages().get().execute.return_value = {
            "payload": {"headers": []},
            "snippet": "",
        }
        result = get_message_summary(service, "msg1")
        assert result["subject"] == "(no subject)"
        assert result["sender"] == "(unknown sender)"


class TestListInboxMessageIds:
    def test_paginates_until_max_results(self):
        service = make_service()
        list_calls = service.users().messages().list
        list_next = service.users().messages().list_next

        first_page = {"messages": [{"id": "a"}, {"id": "b"}]}
        second_page = {"messages": [{"id": "c"}]}
        list_calls.return_value.execute.side_effect = [first_page, second_page]
        list_next.side_effect = [list_calls.return_value, None]

        result = list_inbox_message_ids(service, "in:inbox", max_results=10)
        assert result == ["a", "b", "c"]

    def test_stops_early_once_max_results_reached(self):
        service = make_service()
        service.users().messages().list.return_value.execute.return_value = {
            "messages": [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        }
        result = list_inbox_message_ids(service, "in:inbox", max_results=2)
        assert result == ["a", "b"]


class TestApplyLabels:
    def test_adds_labels_and_removes_inbox(self):
        service = make_service()
        apply_labels(service, "msg1", ["l1", "l2"])
        service.users().messages().modify.assert_called_with(
            userId="me",
            id="msg1",
            body={"addLabelIds": ["l1", "l2"], "removeLabelIds": ["INBOX"]},
        )


class TestRun:
    def _service_with_labels_and_messages(self, labels, message_ids):
        service = make_service()
        service.users().labels().list().execute.return_value = {"labels": labels}
        service.users().messages().list().execute.return_value = {
            "messages": [{"id": mid} for mid in message_ids]
        }
        service.users().messages().list_next.return_value = None
        return service

    @patch("label_inbox.get_gmail_service")
    @patch("label_inbox.classify_email")
    def test_dry_run_never_calls_modify(self, mock_classify, mock_get_service):
        service = self._service_with_labels_and_messages(
            labels=[{"id": "l1", "name": "Work", "type": "user"}],
            message_ids=["m1"],
        )
        service.users().messages().get().execute.return_value = {
            "payload": {"headers": []},
            "snippet": "",
        }
        mock_get_service.return_value = service
        mock_classify.return_value = ["Work"]

        run(
            query="in:inbox",
            max_results=10,
            dry_run=True,
            model="llama3",
            ollama_host="http://localhost:11434",
            credentials_path="credentials.json",
            token_path="token.json",
        )

        service.users().messages().modify.assert_not_called()

    @patch("label_inbox.get_gmail_service")
    @patch("label_inbox.classify_email")
    def test_applies_labels_when_not_dry_run(self, mock_classify, mock_get_service):
        service = self._service_with_labels_and_messages(
            labels=[{"id": "l1", "name": "Work", "type": "user"}],
            message_ids=["m1"],
        )
        service.users().messages().get().execute.return_value = {
            "payload": {"headers": []},
            "snippet": "",
        }
        mock_get_service.return_value = service
        mock_classify.return_value = ["Work"]

        run(
            query="in:inbox",
            max_results=10,
            dry_run=False,
            model="llama3",
            ollama_host="http://localhost:11434",
            credentials_path="credentials.json",
            token_path="token.json",
        )

        service.users().messages().modify.assert_called_with(
            userId="me",
            id="m1",
            body={"addLabelIds": ["l1"], "removeLabelIds": ["INBOX"]},
        )

    @patch("label_inbox.get_gmail_service")
    @patch("label_inbox.classify_email")
    def test_no_matching_label_skips_message(self, mock_classify, mock_get_service):
        service = self._service_with_labels_and_messages(
            labels=[{"id": "l1", "name": "Work", "type": "user"}],
            message_ids=["m1"],
        )
        service.users().messages().get().execute.return_value = {
            "payload": {"headers": []},
            "snippet": "",
        }
        mock_get_service.return_value = service
        mock_classify.return_value = []

        run(
            query="in:inbox",
            max_results=10,
            dry_run=False,
            model="llama3",
            ollama_host="http://localhost:11434",
            credentials_path="credentials.json",
            token_path="token.json",
        )

        service.users().messages().modify.assert_not_called()

    @patch("label_inbox.get_gmail_service")
    def test_no_user_labels_exits_without_listing_messages(self, mock_get_service):
        service = self._service_with_labels_and_messages(labels=[], message_ids=[])
        mock_get_service.return_value = service

        run(
            query="in:inbox",
            max_results=10,
            dry_run=False,
            model="llama3",
            ollama_host="http://localhost:11434",
            credentials_path="credentials.json",
            token_path="token.json",
        )

        service.users().messages().list().execute.assert_not_called()
