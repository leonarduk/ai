# GitHub MCP Server

A Model Context Protocol (MCP) server for interacting with GitHub repositories via the GitHub REST API.

## Features

Comprehensive GitHub operations including repository management, pull requests, issues, file access, and **PR code review capabilities**.

### Available Tools

**Repository Operations:**
- **get_repo_info** - Get detailed information about a repository
- **list_branches** - List all branches in a repository
- **search_repositories** - Search for GitHub repositories
- **get_file_content** - Get the content of a file from a repository
- **list_commits** - List commits in a repository

**Pull Requests:**
- **list_pull_requests** - List pull requests (open, closed, or all)
- **create_pull_request** - Create a new pull request
- **get_pull_request** - Get details of a specific pull request (includes head SHA for review comments)

**PR Review (New):**
- **get_pr_files** - Get list of files changed in a PR with diffs, additions, deletions
- **get_pr_diff** - Get the full unified diff for a pull request
- **create_pr_review_comment** - Add inline review comment to specific line in PR
- **submit_pr_review** - Submit a PR review (APPROVE, REQUEST_CHANGES, or COMMENT)
- **list_pr_comments** - List all review comments on a pull request

**Issues:**
- **list_issues** - List issues in a repository
- **create_issue** - Create a new issue with optional labels

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Add your GitHub Personal Access Token to your `.env` file:

```
GITHUB_TOKEN=your_github_personal_access_token
```

Get a token at: https://github.com/settings/tokens

### Required Permissions

Your GitHub token needs the following scopes:
- `repo` - Full control of private repositories (required for PR reviews)
- `read:org` - Read org and team membership (if accessing org repos)

## Usage

### Repository Format

Tools accept repositories in two formats:
- **URL format:** `https://github.com/owner/repo`
- **Short format:** `owner/repo`

### Examples

**Get repository information:**
```json
{
  "repo": "anthropics/anthropic-sdk-python"
}
```

**List branches:**
```json
{
  "repo": "facebook/react"
}
```

**Create a pull request:**
```json
{
  "repo": "owner/repo",
  "title": "Add new feature",
  "body": "This PR adds...",
  "head": "feature-branch",
  "base": "main"
}
```

### PR Review Workflow

**1. List open PRs:**
```json
{
  "repo": "owner/repo",
  "state": "open"
}
```

**2. Get PR details (includes head SHA needed for comments):**
```json
{
  "repo": "owner/repo",
  "pr_number": 123
}
```

**3. Get files changed in PR with diffs:**
```json
{
  "repo": "owner/repo",
  "pr_number": 123
}
```

**4. Get full unified diff (alternative to get_pr_files):**
```json
{
  "repo": "owner/repo",
  "pr_number": 123
}
```

**5. Add inline review comment:**
```json
{
  "repo": "owner/repo",
  "pr_number": 123,
  "body": "Consider refactoring this for better readability",
  "commit_id": "abc123def456",
  "path": "src/app.py",
  "line": 42
}
```

**6. Submit review with approval/changes/comment:**
```json
{
  "repo": "owner/repo",
  "pr_number": 123,
  "body": "Overall looks good, minor suggestions above",
  "event": "APPROVE"
}
```
Events: `APPROVE`, `REQUEST_CHANGES`, `COMMENT`

**7. List existing review comments:**
```json
{
  "repo": "owner/repo",
  "pr_number": 123
}
```

### Other Examples

**Create an issue:**
```json
{
  "repo": "owner/repo",
  "title": "Bug: Application crashes on startup",
  "body": "Steps to reproduce:\n1. Launch app\n2. ...",
  "labels": ["bug", "high-priority"]
}
```

**Get file content:**
```json
{
  "repo": "owner/repo",
  "path": "src/main.py",
  "ref": "main"
}
```

**Search repositories:**
```json
{
  "query": "language:python stars:>1000",
  "sort": "stars",
  "per_page": 10
}
```

## Interactive AI PR Review Use Case

This server enables AI-powered PR reviews in LM Suite or similar tools:

1. **List PRs** → AI shows open PRs
2. **User selects PR** → AI fetches PR details and file changes
3. **AI analyzes code** → Reviews diffs, identifies issues, suggests improvements
4. **AI posts comments** → Inline comments on specific lines
5. **AI submits review** → Final approval/request changes/comment

## Testing

Run the test suite:

```bash
pytest test_pr_review.py -v
```

Tests cover:
- PR file listing with diffs
- Getting unified diffs
- Creating inline review comments
- Submitting reviews (approve/request changes/comment)
- Listing review comments
- Complete review workflow integration

## Error Handling

The server provides clear error messages for:
- Invalid GitHub tokens
- API rate limiting
- Repository not found
- Insufficient permissions
- Network issues
- Invalid commit IDs or file paths

## Rate Limits

GitHub API rate limits:
- **Authenticated:** 5,000 requests per hour
- **Unauthenticated:** 60 requests per hour

Always use a token for better rate limits.

## Notes

- All API responses are formatted as JSON
- File contents are automatically decoded from base64
- Pull request and issue lists include key metadata for easy filtering
- The server uses GitHub API v3 (REST)
- PR review comments require the commit SHA from `get_pull_request` → `head_sha`
- Line numbers in review comments refer to diff line positions, not file line numbers