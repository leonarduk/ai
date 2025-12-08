
import asyncio
import json
import requests
from typing import Optional
from mcp.server import Server
from mcp.types import Tool, TextContent
from urllib.parse import urlencode

app = Server("internet-search-server")

# Base URL for DuckDuckGo Instant Answer API
DUCKDUCKGO_API = "https://api.duckduckgo.com/"

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_web",
            description="Search the internet using DuckDuckGo",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "format": {"type": "string", "description": "Response format: text or json", "default": "text"}
                },
                "required": ["query"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "search_web":
            query = arguments["query"]
            fmt = arguments.get("format", "text")

            params = {
                "q": query,
                "format": "json",
                "no_redirect": 1,
                "no_html": 1
            }

            response = requests.get(DUCKDUCKGO_API, params=params)
            response.raise_for_status()
            data = response.json()

            # Extract useful info
            abstract = data.get("AbstractText")
            heading = data.get("Heading")
            related_topics = data.get("RelatedTopics", [])

            if fmt == "json":
                return [TextContent(type="text", text=json.dumps(data, indent=2))]
            else:
                result_lines = []
                if heading:
                    result_lines.append(f"**{heading}**")
                if abstract:
                    result_lines.append(abstract)
                if related_topics:
                    result_lines.append("\nRelated:")
                    for topic in related_topics[:5]:
                        if "Text" in topic and "FirstURL" in topic:
                            result_lines.append(f"- {topic['Text']} ({topic['FirstURL']})")

                text_result = "\n".join(result_lines) if result_lines else "No results found."
                return [TextContent(type="text", text=text_result)]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except requests.exceptions.HTTPError as e:
        return [TextContent(type="text", text=f"HTTP error: {e.response.status_code}")]
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
