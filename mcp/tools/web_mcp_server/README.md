# Web MCP Server

This MCP server provides web search and content fetching capabilities for LLMs.

## Features

- **Web Search**: Real web search using Brave Search API
- **Web Fetch**: Extract clean text content from any web page

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Add your Brave Search API key to your `.env` file:

```
BRAVE_API_KEY=your_api_key_here
```

Get a free API key at: https://brave.com/search/api/ (2,000 queries/month free tier)

## Tools

### web_search
Search the web and get relevant results with titles, URLs, and descriptions.

**Parameters:**
- `query` (required): Search query string
- `count` (optional): Number of results (default: 10, max: 20)
- `offset` (optional): Pagination offset (default: 0)

**Example:**
```json
{
  "query": "Python MCP servers",
  "count": 5
}
```

### web_fetch
Fetch and extract clean text content from a web page.

**Parameters:**
- `url` (required): URL of the page to fetch
- `include_html` (optional): Include raw HTML in response (default: false)

**Example:**
```json
{
  "url": "https://example.com/article"
}
```

## Usage

Run the server:

```bash
python server.py
```

The server communicates via stdio using the MCP protocol.
