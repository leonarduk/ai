# MCP Servers - Architecture Overview

Consolidated MCP server collection for LM Studio with clear separation of concerns and no duplication.

## Server Inventory (7 Total)

### 1. **email** - Email & Task Management
- **Path:** `email-mcp-server/`
- **Tools:** `send_email`, `create_todoist_task`
- **Purpose:** Send emails via SMTP and create Todoist tasks
- **Dependencies:** Built-in smtplib
- **Env Vars:** `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `TODOIST_EMAIL`

### 2. **filesystem** - File Operations
- **Path:** `filesystem-mcp-server/`
- **Tools:** `read_file`, `write_file`, `edit_file`, `list_directory`, `create_directory`, `search_files`, `get_file_info`, `csv_read`, `csv_write`, `excel_read`, `excel_write`, `zip_compress`, `zip_decompress`, `gzip_compress`, `gzip_decompress`
- **Purpose:** All file system operations including CSV, Excel, and compression
- **Dependencies:** pandas, openpyxl
- **Env Vars:** None

### 3. **git** - Local Git Operations
- **Path:** `git-mcp-server/`
- **Tools:** `git_status`, `git_add`, `git_commit`, `git_push`, `git_pull`, `git_branch`, `git_checkout`, `git_log`, `git_diff`
- **Purpose:** Local git repository operations via subprocess
- **Dependencies:** None (uses subprocess)
- **Env Vars:** None

### 4. **github** - GitHub API
- **Path:** `github-mcp-server/`
- **Tools:** `get_repo_info`, `list_branches`, `list_pull_requests`, `create_pull_request`, `get_pull_request`, `list_issues`, `create_issue`, `get_file_content`, `list_commits`, `search_repositories`
- **Purpose:** Interact with GitHub repositories via REST API
- **Dependencies:** requests, python-dotenv
- **Env Vars:** `GITHUB_TOKEN`

### 5. **data_format** - Data Transformation
- **Path:** `data_format_mcp_server/`
- **Tools:** `json_parse`, `json_generate`, `json_validate`, `xml_parse`, `xml_generate`, `xml_validate`
- **Purpose:** Parse and generate JSON/XML data structures
- **Dependencies:** None (uses built-in json and xml.etree)
- **Env Vars:** None

### 6. **os_info** - System Monitoring
- **Path:** `os_info_mcp_server/`
- **Tools:** `get_cpu_usage`, `get_memory_usage`, `get_system_info`
- **Purpose:** Monitor CPU and memory usage
- **Dependencies:** psutil
- **Env Vars:** None

### 7. **web** - Web Search & Fetch
- **Path:** `web_mcp_server/`
- **Tools:** `web_search`, `web_fetch`
- **Purpose:** Search the web (Brave API) and fetch/parse web page content
- **Dependencies:** requests, beautifulsoup4
- **Env Vars:** `BRAVE_API_KEY`

## Configuration

All servers are registered in `mcpSettings.json` and use the shared virtual environment at `C:\Users\steph\workspace\GitHub\ai\.venv`.

## Installation

```bash
# Install all dependencies
cd C:\Users\steph\workspace\GitHub\ai
pip install -r tools/data_format_mcp_server/requirements.txt
pip install -r tools/email-mcp-server/requirements.txt
pip install -r tools/filesystem-mcp-server/requirements.txt
pip install -r tools/git-mcp-server/requirements.txt
pip install -r tools/github-mcp-server/requirements.txt
pip install -r tools/os_info_mcp_server/requirements.txt
pip install -r tools/web_mcp_server/requirements.txt
```

## Environment Variables

Create/update `.env` file at `C:\Users\steph\workspace\GitHub\ai/.env`:

```
# GitHub API
GITHUB_TOKEN=your_github_token_here

# Brave Search API (2000 free queries/month)
BRAVE_API_KEY=your_brave_api_key_here

# Email/SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Todoist (optional)
TODOIST_EMAIL=your-unique-email@todoist.com
```

## Architecture Changes

### Merged Servers (Eliminated Duplication)
- ✅ `file_processing` → merged into `filesystem`
- ✅ `todoist` → merged into `email`
- ✅ `web_api` + `web_query` → consolidated into `web`

### Deleted Servers (Duplicates)
- ❌ `local-file-access` (duplicate of filesystem)
- ❌ `data_operations` (unused/overlapping functionality)

### Result
- **Before:** 11 servers with significant duplication
- **After:** 7 servers with clear boundaries
- **Code reduction:** ~500+ lines of duplicated code eliminated

## Best Practices Applied

1. **Single Responsibility:** Each server has one clear purpose
2. **No Duplication:** Related functionality consolidated
3. **Consistent Structure:** All servers follow same pattern (server.py, requirements.txt, README.md)
4. **Environment Configuration:** Shared .env file for all secrets
5. **Clear Documentation:** Each server has comprehensive README

## Future Considerations

- Consider removing `os_info` if system monitoring isn't actively used
- All servers are production-ready for LM Studio integration
