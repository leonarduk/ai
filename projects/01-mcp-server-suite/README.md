# MCP Server Suite

**Production-ready Model Context Protocol servers enabling LLM tool use.**

## Overview

This project implements 7 specialized MCP servers that provide LLMs with structured access to external systems and data sources. Each server handles a specific domain, maintaining clear separation of concerns and independent deployment.

## Architecture

### Why Multiple Servers?

Instead of a monolithic server with all tools, we chose domain-specific servers for:
- **Independent deployment** - Update one server without affecting others
- **Clear boundaries** - Single responsibility per server
- **Resource isolation** - File operations don't impact API calls
- **Security isolation** - Different permission scopes per server

See [ADR-001](./docs/adr-001-multi-server-architecture.md) for detailed decision rationale.

## Server Inventory

### 1. GitHub MCP Server
**Purpose:** Interact with GitHub repositories via REST API  
**Tools:** Repository info, PR management, issue tracking, file operations  
**Key Features:**
- Rate limiting with exponential backoff
- Response caching for read operations
- Comprehensive error handling

[Documentation](./servers/github-mcp-server/README.md)

### 2. Filesystem MCP Server
**Purpose:** File system operations with security controls  
**Tools:** Read/write files, directory operations, CSV/Excel, compression  
**Key Features:**
- Path traversal protection
- File size limits
- Audit logging for destructive operations

[Documentation](./servers/filesystem-mcp-server/README.md)

### 3. Git MCP Server
**Purpose:** Local git repository operations  
**Tools:** Status, add, commit, push, pull, branch management  
**Key Features:**
- Subprocess-based git commands
- Working directory validation

[Documentation](./servers/git-mcp-server/README.md)

### 4. Email MCP Server
**Purpose:** Email sending and task management  
**Tools:** SMTP email, Todoist task creation  
**Key Features:**
- Template support
- Attachment handling
- Task integration

[Documentation](./servers/email-mcp-server/README.md)

### 5. Web MCP Server
**Purpose:** Web search and content retrieval  
**Tools:** Brave API search, webpage fetching/parsing  
**Key Features:**
- BeautifulSoup content extraction
- Search result ranking

[Documentation](./servers/web-mcp-server/README.md)

### 6. Data Format MCP Server
**Purpose:** Parse and generate structured data  
**Tools:** JSON/XML parsing, validation, generation  
**Key Features:**
- Schema validation
- Format conversion

[Documentation](./servers/data-format-mcp-server/README.md)

### 7. OS Info MCP Server
**Purpose:** System monitoring and metrics  
**Tools:** CPU usage, memory usage, system info  
**Key Features:**
- Real-time metrics
- Cross-platform support

[Documentation](./servers/os-info-mcp-server/README.md)

## Quick Start

### Prerequisites
- Python 3.11+
- pip and virtualenv

### Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
cd servers/github-mcp-server
pip install -r requirements.txt
# Repeat for other servers as needed
```

### Configuration

Create `.env` file in project root:

```bash
# GitHub API
GITHUB_TOKEN=your_github_token_here

# Brave Search API (2000 free queries/month)
BRAVE_API_KEY=your_brave_api_key_here

# Email/SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Todoist
TODOIST_EMAIL=your-unique-email@todoist.com
```

### Running a Server

```bash
cd servers/github-mcp-server
python server.py
```

## Development

### Testing

```bash
# Run tests for a specific server
cd servers/github-mcp-server
pytest tests/ -v --cov=server

# Run all tests
pytest servers/*/tests/ -v
```

### Code Quality

```bash
# Linting
flake8 servers/
black servers/ --check

# Security scanning
bandit -r servers/
```

## Project Structure

```
01-mcp-server-suite/
├── README.md                    # This file
├── docs/                        # Architecture & design docs
│   ├── adr-001-multi-server-architecture.md
│   ├── api-reference.md
│   └── troubleshooting.md
├── servers/                     # Server implementations
│   ├── github-mcp-server/
│   ├── filesystem-mcp-server/
│   ├── git-mcp-server/
│   ├── email-mcp-server/
│   ├── web-mcp-server/
│   ├── data-format-mcp-server/
│   └── os-info-mcp-server/
└── shared/                      # Common utilities (future)
    ├── auth.py
    ├── logging.py
    └── retry.py
```

## Technology Stack

- **Language:** Python 3.11+
- **Framework:** MCP Protocol (Model Context Protocol)
- **APIs:** GitHub REST API, Brave Search API, SMTP
- **Libraries:** 
  - `mcp` - MCP protocol implementation
  - `requests` - HTTP client
  - `pandas`, `openpyxl` - Data processing
  - `beautifulsoup4` - HTML parsing
  - `psutil` - System monitoring

## Status

**Current Phase:** Production-ready, actively maintained

**Known Issues:**
- Rate limiting needs tuning for high-volume usage
- Cache invalidation strategy needs refinement
- Some servers lack comprehensive integration tests

**Roadmap:**
- [ ] Add Redis-based caching layer
- [ ] Implement circuit breaker pattern
- [ ] Add OpenTelemetry instrumentation
- [ ] Create shared utility library
- [ ] Add Terraform deployment configs

## Contributing

This is a personal portfolio project, but suggestions and feedback are welcome via issues.

## License

MIT License - see [LICENSE](../../LICENSE) for details

## Contact

**LinkedIn:** [linkedin.com/in/leonarduk](https://www.linkedin.com/in/leonarduk)

---

*Part of the [AI Systems Lab](../../README.md) portfolio*
