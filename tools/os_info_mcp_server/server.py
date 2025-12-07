#!/usr/bin/env python3
"""
MCP (Model Control Protocol) Tool for CPU and Memory Monitoring
This tool integrates with MCP protocol to provide system monitoring capabilities.
"""

import asyncio
import json
import psutil
from pathlib import Path
from typing import Optional
from mcp.server import Server
from mcp.types import Tool, TextContent

# Create the MCP server
app = Server("cpu-memory-monitor")

def format_bytes(bytes_value):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_cpu_usage",
            description="Get current CPU usage percentage",
            inputSchema={
                "type": "object",
                "properties": {
                    "interval": {"type": "number", "description": "Sampling interval in seconds (default: 1)"},
                },
                "required": []
            }
        ),
        Tool(
            name="get_memory_usage",
            description="Get current memory usage information",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_system_info",
            description="Get comprehensive system CPU and memory information",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "get_cpu_usage":
            interval = arguments.get("interval", 1)
            cpu_percent = psutil.cpu_percent(interval=interval)
            result = {
                "cpu_percentage": cpu_percent,
                "timestamp": asyncio.get_event_loop().time()
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "get_memory_usage":
            memory = psutil.virtual_memory()
            result = {
                "total": memory.total,
                "available": memory.available,
                "used": memory.used,
                "percent": memory.percent,
                "free": memory.free,
                "active": memory.active,
                "inactive": memory.inactive,
                "timestamp": asyncio.get_event_loop().time()
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "get_system_info":
            # Get CPU info
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Get memory info
            memory = psutil.virtual_memory()
            
            result = {
                "cpu": {
                    "percentage": cpu_percent,
                    "count_logical": psutil.cpu_count(logical=True),
                    "count_physical": psutil.cpu_count(logical=False),
                },
                "memory": {
                    "total_bytes": memory.total,
                    "available_bytes": memory.available,
                    "used_bytes": memory.used,
                    "percent": memory.percent,
                    "free_bytes": memory.free,
                },
                "formatted": {
                    "memory_total": format_bytes(memory.total),
                    "memory_available": format_bytes(memory.available),
                    "memory_used": format_bytes(memory.used),
                },
                "timestamp": asyncio.get_event_loop().time()
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
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