import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from server import parse_repo, call_tool
from mcp.types import TextContent


# Fixtures
@pytest.fixture
def mock_env(monkeypatch):
    """Mock environment variable for GitHub token"""
    monkeypatch.setenv("GITHUB_TOKEN", "test_token_12345")


@pytest.fixture
def mock_response():
    """Create a mock response object"""

    def _mock_response(status_code=200, json_data=None, text_data=None):
        mock = Mock()
        mock.status_code = status_code
        mock.json.return_value = json_data if json_data else {}
        mock.text = text_data if text_data else ""
        mock.raise_for_status = Mock()
        return mock

    return _mock_response


# Test parse_repo function
def test_parse_repo_url():
    owner, repo = parse_repo("https://github.com/facebook/react")
    assert owner == "facebook"
    assert repo == "react"


def test_parse_repo_short_format():
    owner, repo = parse_repo("facebook/react")
    assert owner == "facebook"
    assert repo == "react"


def test_parse_repo_with_trailing_slash():
    owner, repo = parse_repo("https://github.com/facebook/react/")
    assert owner == "facebook"
    assert repo == "react"


# Test get_pr_files
@pytest.mark.asyncio
async def test_get_pr_files(mock_env, mock_response):
    files_data = [
        {
            "filename": "src/app.py",
            "status": "modified",
            "additions": 10,
            "deletions": 5,
            "changes": 15,
            "patch": "@@ -1,5 +1,10 @@\n-old line\n+new line"
        },
        {
            "filename": "tests/test_app.py",
            "status": "added",
            "additions": 50,
            "deletions": 0,
            "changes": 50,
            "patch": "@@ -0,0 +1,50 @@\n+new test file"
        }
    ]

    with patch('requests.get') as mock_get:
        mock_get.return_value = mock_response(json_data=files_data)

        result = await call_tool("get_pr_files", {
            "repo": "owner/repo",
            "pr_number": 123
        })

        assert len(result) == 1
        assert isinstance(result[0], TextContent)

        parsed = json.loads(result[0].text)
        assert len(parsed) == 2
        assert parsed[0]["filename"] == "src/app.py"
        assert parsed[0]["status"] == "modified"
        assert parsed[0]["additions"] == 10
        assert parsed[1]["filename"] == "tests/test_app.py"
        assert parsed[1]["status"] == "added"

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert "repos/owner/repo/pulls/123/files" in args[0]


# Test get_pr_diff
@pytest.mark.asyncio
async def test_get_pr_diff(mock_env, mock_response):
    diff_text = """diff --git a/src/app.py b/src/app.py
index abc123..def456 100644
--- a/src/app.py
+++ b/src/app.py
@@ -1,5 +1,10 @@
-old line
+new line
"""

    with patch('requests.get') as mock_get:
        mock_get.return_value = mock_response(text_data=diff_text)

        result = await call_tool("get_pr_diff", {
            "repo": "owner/repo",
            "pr_number": 123
        })

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "diff --git" in result[0].text
        assert "src/app.py" in result[0].text

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert kwargs["headers"]["Accept"] == "application/vnd.github.v3.diff"


# Test create_pr_review_comment
@pytest.mark.asyncio
async def test_create_pr_review_comment(mock_env, mock_response):
    comment_response = {
        "id": 12345,
        "html_url": "https://github.com/owner/repo/pull/123#discussion_r12345",
        "path": "src/app.py",
        "line": 42,
        "body": "This needs improvement"
    }

    with patch('requests.post') as mock_post:
        mock_post.return_value = mock_response(json_data=comment_response)

        result = await call_tool("create_pr_review_comment", {
            "repo": "owner/repo",
            "pr_number": 123,
            "body": "This needs improvement",
            "commit_id": "abc123def456",
            "path": "src/app.py",
            "line": 42
        })

        assert len(result) == 1
        assert "Created review comment" in result[0].text
        assert "src/app.py:42" in result[0].text
        assert comment_response["html_url"] in result[0].text

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "repos/owner/repo/pulls/123/comments" in args[0]
        assert kwargs["json"]["body"] == "This needs improvement"
        assert kwargs["json"]["commit_id"] == "abc123def456"
        assert kwargs["json"]["path"] == "src/app.py"
        assert kwargs["json"]["line"] == 42


# Test submit_pr_review
@pytest.mark.asyncio
async def test_submit_pr_review_approve(mock_env, mock_response):
    review_response = {
        "id": 67890,
        "html_url": "https://github.com/owner/repo/pull/123#pullrequestreview-67890",
        "state": "APPROVED"
    }

    with patch('requests.post') as mock_post:
        mock_post.return_value = mock_response(json_data=review_response)

        result = await call_tool("submit_pr_review", {
            "repo": "owner/repo",
            "pr_number": 123,
            "body": "Looks good!",
            "event": "APPROVE"
        })

        assert len(result) == 1
        assert "Submitted APPROVE review" in result[0].text
        assert "PR #123" in result[0].text
        assert review_response["html_url"] in result[0].text

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "repos/owner/repo/pulls/123/reviews" in args[0]
        assert kwargs["json"]["event"] == "APPROVE"
        assert kwargs["json"]["body"] == "Looks good!"


@pytest.mark.asyncio
async def test_submit_pr_review_request_changes(mock_env, mock_response):
    review_response = {
        "id": 67891,
        "html_url": "https://github.com/owner/repo/pull/123#pullrequestreview-67891",
        "state": "CHANGES_REQUESTED"
    }

    with patch('requests.post') as mock_post:
        mock_post.return_value = mock_response(json_data=review_response)

        result = await call_tool("submit_pr_review", {
            "repo": "owner/repo",
            "pr_number": 123,
            "body": "Please fix the issues",
            "event": "REQUEST_CHANGES"
        })

        assert len(result) == 1
        assert "Submitted REQUEST_CHANGES review" in result[0].text

        kwargs = mock_post.call_args[1]
        assert kwargs["json"]["event"] == "REQUEST_CHANGES"


# Test list_pr_comments
@pytest.mark.asyncio
async def test_list_pr_comments(mock_env, mock_response):
    comments_data = [
        {
            "id": 1,
            "user": {"login": "reviewer1"},
            "path": "src/app.py",
            "line": 10,
            "body": "Consider using list comprehension here",
            "created_at": "2024-01-01T10:00:00Z"
        },
        {
            "id": 2,
            "user": {"login": "reviewer2"},
            "path": "src/utils.py",
            "line": 25,
            "body": "Add type hints",
            "created_at": "2024-01-01T11:00:00Z"
        }
    ]

    with patch('requests.get') as mock_get:
        mock_get.return_value = mock_response(json_data=comments_data)

        result = await call_tool("list_pr_comments", {
            "repo": "owner/repo",
            "pr_number": 123
        })

        assert len(result) == 1
        parsed = json.loads(result[0].text)
        assert len(parsed) == 2
        assert parsed[0]["author"] == "reviewer1"
        assert parsed[0]["path"] == "src/app.py"
        assert parsed[0]["line"] == 10
        assert parsed[1]["author"] == "reviewer2"


# Test get_pull_request includes head_sha
@pytest.mark.asyncio
async def test_get_pull_request_includes_head_sha(mock_env, mock_response):
    pr_data = {
        "number": 123,
        "title": "Add feature",
        "body": "Description",
        "state": "open",
        "user": {"login": "author"},
        "head": {"ref": "feature-branch", "sha": "abc123def456"},
        "base": {"ref": "main"},
        "html_url": "https://github.com/owner/repo/pull/123",
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-01T11:00:00Z",
        "mergeable": True,
        "merged": False
    }

    with patch('requests.get') as mock_get:
        mock_get.return_value = mock_response(json_data=pr_data)

        result = await call_tool("get_pull_request", {
            "repo": "owner/repo",
            "pr_number": 123
        })

        parsed = json.loads(result[0].text)
        assert parsed["head_sha"] == "abc123def456"
        assert parsed["head"] == "feature-branch"


# Test error handling
@pytest.mark.asyncio
async def test_pr_review_api_error(mock_env):
    with patch('requests.post') as mock_post:
        error_response = Mock()
        error_response.status_code = 422
        error_response.json.return_value = {"message": "Validation Failed"}
        error_response.raise_for_status.side_effect = Exception()
        mock_post.return_value = error_response

        result = await call_tool("create_pr_review_comment", {
            "repo": "owner/repo",
            "pr_number": 123,
            "body": "Comment",
            "commit_id": "invalid",
            "path": "src/app.py",
            "line": 1
        })

        assert "Error:" in result[0].text


# Integration test scenario
@pytest.mark.asyncio
async def test_pr_review_workflow(mock_env, mock_response):
    """Test a complete PR review workflow"""

    # Step 1: Get PR details
    pr_data = {
        "number": 123,
        "title": "Add feature",
        "body": "Description",
        "state": "open",
        "user": {"login": "author"},
        "head": {"ref": "feature", "sha": "abc123"},
        "base": {"ref": "main"},
        "html_url": "https://github.com/owner/repo/pull/123",
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-01T11:00:00Z",
        "mergeable": True,
        "merged": False
    }

    # Step 2: Get files
    files_data = [{
        "filename": "src/app.py",
        "status": "modified",
        "additions": 10,
        "deletions": 5,
        "changes": 15,
        "patch": "@@ -1,5 +1,10 @@"
    }]

    # Step 3: Submit review
    review_data = {
        "id": 1,
        "html_url": "https://github.com/owner/repo/pull/123#review-1",
        "state": "APPROVED"
    }

    with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
        mock_get.side_effect = [
            mock_response(json_data=pr_data),
            mock_response(json_data=files_data)
        ]
        mock_post.return_value = mock_response(json_data=review_data)

        # Get PR
        pr_result = await call_tool("get_pull_request", {
            "repo": "owner/repo",
            "pr_number": 123
        })
        pr_info = json.loads(pr_result[0].text)
        assert pr_info["head_sha"] == "abc123"

        # Get files
        files_result = await call_tool("get_pr_files", {
            "repo": "owner/repo",
            "pr_number": 123
        })
        files = json.loads(files_result[0].text)
        assert len(files) == 1
        assert files[0]["filename"] == "src/app.py"

        # Submit review
        review_result = await call_tool("submit_pr_review", {
            "repo": "owner/repo",
            "pr_number": 123,
            "body": "LGTM",
            "event": "APPROVE"
        })
        assert "APPROVE" in review_result[0].text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])