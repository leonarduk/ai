# GitHub MCP Server

A Model Context Protocol (MCP) server for interacting with GitHub repositories via the GitHub REST API.

## Features

Comprehensive GitHub operations including repository management, pull requests, issues, and file access.

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
- **get_pull_request** - Get details of a specific pull request

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
- `repo` - Full control of private repositories
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

**List pull requests:**
```json
{
  "repo": "owner/repo",
  "state": "open"
}
```

## Error Handling

The server provides clear error messages for:
- Invalid GitHub tokens
- API rate limiting
- Repository not found
- Insufficient permissions
- Network issues

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
