#!/usr/bin/env python3
"""
MCP Server for web search and fetching
Provides tools for searching the web via Brave Search API and fetching web page content
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from mcp.server import Server
from mcp.types import Tool, TextContent

app = Server("web-server")

def load_env():
    """Load environment variables from .env file"""
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()

load_env()

def get_brave_api_key() -> str:
    """Get Brave Search API key from environment"""
    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        raise ValueError("BRAVE_API_KEY environment variable not set. Get one at https://brave.com/search/api/")
    return api_key

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="web_search",
            description="Search the web using Brave Search API. Returns relevant web results with titles, URLs, and descriptions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of results to return (default: 10, max: 20)",
                        "default": 10
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset (default: 0)",
                        "default": 0
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="web_fetch",
            description="Fetch and extract text content from a web page. Returns the main text content, title, and metadata.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL of the web page to fetch"
                    },
                    "include_html": {
                        "type": "boolean",
                        "description": "Include raw HTML in response (default: false)",
                        "default": False
                    }
                },
                "required": ["url"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "web_search":
            query = arguments["query"]
            count = min(arguments.get("count", 10), 20)  # Cap at 20
            offset = arguments.get("offset", 0)
            
            api_key = get_brave_api_key()
            
            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key
            }
            
            params = {
                "q": query,
                "count": count,
                "offset": offset
            }
            
            response = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers=headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract web results
            results = []
            if "web" in data and "results" in data["web"]:
                for item in data["web"]["results"]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "description": item.get("description", ""),
                        "age": item.get("age", "")
                    })
            
            result = {
                "query": query,
                "total_results": len(results),
                "results": results
            }
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "web_fetch":
            url = arguments["url"]
            include_html = arguments.get("include_html", False)
            
            # Set a user agent to avoid blocks
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Get title
            title = soup.title.string if soup.title else ""
            
            # Get meta description
            meta_desc = ""
            meta_tag = soup.find("meta", attrs={"name": "description"})
            if meta_tag and meta_tag.get("content"):
                meta_desc = meta_tag["content"]
            
            # Extract main text content
            text = soup.get_text(separator="\n", strip=True)
            
            # Clean up excessive newlines
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            cleaned_text = "\n".join(lines)
            
            result = {
                "url": url,
                "title": title,
                "meta_description": meta_desc,
                "content": cleaned_text,
                "content_length": len(cleaned_text)
            }
            
            if include_html:
                result["html"] = response.text
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    except requests.exceptions.Timeout:
        return [TextContent(type="text", text="Error: Request timed out")]
    except requests.exceptions.HTTPError as e:
        return [TextContent(type="text", text=f"HTTP error: {e.response.status_code} - {str(e)}")]
    except ValueError as e:
        return [TextContent(type="text", text=f"Configuration error: {str(e)}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
