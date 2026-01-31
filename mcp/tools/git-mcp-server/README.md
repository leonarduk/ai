# Git MCP Server

A Model Context Protocol (MCP) server for local Git repository operations.

## Features

Execute Git commands on local repositories through a safe subprocess interface.

### Available Tools

- **git_status** - Show the working tree status
- **git_add** - Add file contents to the staging area
- **git_commit** - Record changes to the repository
- **git_push** - Update remote refs along with associated objects
- **git_pull** - Fetch from and integrate with another repository
- **git_branch** - List, create, or delete branches
- **git_checkout** - Switch branches or restore working tree files
- **git_log** - Show commit logs
- **git_diff** - Show changes between commits, commit and working tree, etc.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

All tools require a `repo_path` parameter pointing to a local Git repository.

### Examples

**Check status:**
```json
{
  "repo_path": "C:\\Users\\steph\\workspace\\myproject"
}
```

**Add files:**
```json
{
  "repo_path": "C:\\Users\\steph\\workspace\\myproject",
  "files": "."
}
```

**Commit changes:**
```json
{
  "repo_path": "C:\\Users\\steph\\workspace\\myproject",
  "message": "Add new feature"
}
```

**Push to remote:**
```json
{
  "repo_path": "C:\\Users\\steph\\workspace\\myproject",
  "remote": "origin",
  "branch": "main"
}
```

**Create a branch:**
```json
{
  "repo_path": "C:\\Users\\steph\\workspace\\myproject",
  "action": "create",
  "branch_name": "feature-branch"
}
```

**View commit log:**
```json
{
  "repo_path": "C:\\Users\\steph\\workspace\\myproject",
  "max_count": 10
}
```

## Configuration

No environment variables required. This server uses the `git` command-line tool via subprocess, so Git must be installed and available in your system PATH.

## Notes

- All Git commands are executed with appropriate timeouts to prevent hanging
- The server validates that paths exist and are directories before executing commands
- Commands run in the context of the specified repository path
- Standard Git credentials (SSH keys, credential helpers) are used for authentication

## Security

The server executes Git commands via subprocess but does not allow arbitrary command execution. Only predefined Git operations are permitted.
