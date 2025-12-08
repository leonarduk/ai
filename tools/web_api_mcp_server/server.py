#!/usr/bin/env python3
"""
MCP Server for HTTP/API requests
Provides tools for making HTTP requests to APIs and web services
"""

import asyncio
import json
import os
from pathlib import Path

import aiohttp
from mcp.server import Server
from mcp.types import Tool, TextContent

app = Server("web-api-server")

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

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="http_get",
            description="Make an HTTP GET request",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to request"},
                    "headers": {"type": "object", "description": "Optional HTTP headers"},
                    "params": {"type": "object", "description": "Optional query parameters"}
                },
                "required": ["url"],
                "additionalProperties": False
            }
        ),
        Tool(
            name="http_post",
            description="Make an HTTP POST request",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to request"},
                    "headers": {"type": "object", "description": "Optional HTTP headers"},
                    "json_data": {"type": "object", "description": "JSON data to send"},
                    "form_data": {"type": "object", "description": "Form data to send"}
                },
                "required": ["url"],
                "additionalProperties": False
            }
        ),
        Tool(
            name="http_put",
            description="Make an HTTP PUT request",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to request"},
                    "headers": {"type": "object", "description": "Optional HTTP headers"},
                    "json_data": {"type": "object", "description": "JSON data to send"}
                },
                "required": ["url"],
                "additionalProperties": False
            }
        ),
        Tool(
            name="http_delete",
            description="Make an HTTP DELETE request",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to request"},
                    "headers": {"type": "object", "description": "Optional HTTP headers"}
                },
                "required": ["url"],
                "additionalProperties": False
            }
        ),
        Tool(
            name="http_patch",
            description="Make an HTTP PATCH request",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to request"},
                    "headers": {"type": "object", "description": "Optional HTTP headers"},
                    "json_data": {"type": "object", "description": "JSON data to send"}
                },
                "required": ["url"],
                "additionalProperties": False
            }
        )
    ]

def safe_json_dumps(data: dict, max_length: int = 100000) -> str:
    """Safely serialize data to JSON, handling encoding issues and size limits"""
    try:
        # First attempt: normal serialization
        result = json.dumps(data, indent=2, ensure_ascii=False)
        
        # Truncate if too large
        if len(result) > max_length:
            data_copy = data.copy()
            if 'body' in data_copy:
                body_str = str(data_copy['body'])
                if len(body_str) > max_length - 1000:
                    data_copy['body'] = body_str[:max_length - 1000] + "\n\n[TRUNCATED]"
            result = json.dumps(data_copy, indent=2, ensure_ascii=False)
        
        return result
    except (TypeError, ValueError) as e:
        # Fallback: convert problematic fields to strings
        safe_data = {}
        for key, value in data.items():
            try:
                json.dumps({key: value})
                safe_data[key] = value
            except (TypeError, ValueError):
                safe_data[key] = str(value)
        
        return json.dumps(safe_data, indent=2, ensure_ascii=False)

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        url = arguments["url"]
        headers = arguments.get("headers", {})
        
        async with aiohttp.ClientSession() as session:
            if name == "http_get":
                params = arguments.get("params", {})
                async with session.get(url, headers=headers, params=params) as response:
                    result = {
                        "status": response.status,
                        "headers": dict(response.headers),
                        "body": await response.text()
                    }
                    return [TextContent(type="text", text=safe_json_dumps(result))]
            
            elif name == "http_post":
                json_data = arguments.get("json_data")
                form_data = arguments.get("form_data")
                
                if json_data:
                    async with session.post(url, headers=headers, json=json_data) as response:
                        result = {
                            "status": response.status,
                            "headers": dict(response.headers),
                            "body": await response.text()
                        }
                        return [TextContent(type="text", text=safe_json_dumps(result))]
                elif form_data:
                    async with session.post(url, headers=headers, data=form_data) as response:
                        result = {
                            "status": response.status,
                            "headers": dict(response.headers),
                            "body": await response.text()
                        }
                        return [TextContent(type="text", text=safe_json_dumps(result))]
                else:
                    async with session.post(url, headers=headers) as response:
                        result = {
                            "status": response.status,
                            "headers": dict(response.headers),
                            "body": await response.text()
                        }
                        return [TextContent(type="text", text=safe_json_dumps(result))]
            
            elif name == "http_put":
                json_data = arguments.get("json_data", {})
                async with session.put(url, headers=headers, json=json_data) as response:
                    result = {
                        "status": response.status,
                        "headers": dict(response.headers),
                        "body": await response.text()
                    }
                    return [TextContent(type="text", text=safe_json_dumps(result))]
            
            elif name == "http_delete":
                async with session.delete(url, headers=headers) as response:
                    result = {
                        "status": response.status,
                        "headers": dict(response.headers),
                        "body": await response.text()
                    }
                    return [TextContent(type="text", text=safe_json_dumps(result))]
            
            elif name == "http_patch":
                json_data = arguments.get("json_data", {})
                async with session.patch(url, headers=headers, json=json_data) as response:
                    result = {
                        "status": response.status,
                        "headers": dict(response.headers),
                        "body": await response.text()
                    }
                    return [TextContent(type="text", text=safe_json_dumps(result))]
            
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
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
