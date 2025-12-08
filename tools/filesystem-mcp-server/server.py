
import asyncio
import os
import json
from pathlib import Path
from typing import Optional
from mcp.server import Server
from mcp.types import Tool, TextContent

# Configure allowed directories
ALLOWED_DIRS = [
    Path(r"C:\Users\steph\workspace")
]

app = Server("filesystem-server")

def is_path_allowed(path: Path) -> bool:
    """Check if path is within allowed directories"""
    try:
        resolved = path.resolve()
        return any(resolved.is_relative_to(allowed) for allowed in ALLOWED_DIRS)
    except (ValueError, OSError):
        return False

def safe_path(path_str: str) -> Optional[Path]:
    """Convert string to Path and validate it's allowed"""
    path = Path(path_str)
    if is_path_allowed(path):
        return path
    raise ValueError(f"Access denied: {path_str} is outside allowed directories")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="read_file",
            description="Read the complete contents of a file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="write_file",
            description="Write content to a file (creates or overwrites)",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["path", "content"]
            }
        ),
        Tool(
            name="edit_file",
            description="Edit a file by adding, deleting, or replacing a specific line",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"},
                    "action": {"type": "string", "description": "Action: add, delete, replace"},
                    "line_number": {"type": "integer", "description": "Line number (1-based index)"},
                    "content": {"type": "string", "description": "Content for add or replace", "default": ""}
                },
                "required": ["path", "action", "line_number"]
            }
        ),
        Tool(
            name="list_directory",
            description="List all files and directories in a path",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="create_directory",
            description="Create a new directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to create"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="search_files",
            description="Search for files by name pattern",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory to search in"},
                    "pattern": {"type": "string", "description": "Filename pattern to match"}
                },
                "required": ["path", "pattern"]
            }
        ),
        Tool(
            name="get_file_info",
            description="Get metadata about a file or directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to check"}
                },
                "required": ["path"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "read_file":
            path = safe_path(arguments["path"])
            content = path.read_text(encoding='utf-8')
            return [TextContent(type="text", text=content)]

        elif name == "write_file":
            path = safe_path(arguments["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(arguments["content"], encoding='utf-8')
            return [TextContent(type="text", text=f"Successfully wrote to {path}")]

        elif name == "edit_file":
            path = safe_path(arguments["path"])
            action = arguments["action"]
            line_number = arguments["line_number"]
            content = arguments.get("content", "")

            if not path.exists() or not path.is_file():
                return [TextContent(type="text", text=f"Error: {path} does not exist or is not a file")]

            lines = path.read_text(encoding='utf-8').splitlines()

            if line_number < 1 or line_number > len(lines) + 1:
                return [TextContent(type="text", text=f"Invalid line number: {line_number}")]

            if action == "add":
                lines.insert(line_number - 1, content)
            elif action == "delete":
                if line_number <= len(lines):
                    lines.pop(line_number - 1)
                else:
                    return [TextContent(type="text", text=f"Cannot delete: line {line_number} does not exist")]
            elif action == "replace":
                if line_number <= len(lines):
                    lines[line_number - 1] = content
                else:
                    return [TextContent(type="text", text=f"Cannot replace: line {line_number} does not exist")]
            else:
                return [TextContent(type="text", text=f"Unknown action: {action}")]

            path.write_text("\n".join(lines), encoding='utf-8')
            return [TextContent(type="text", text=f"Successfully performed {action} on line {line_number} in {path}")]

        elif name == "list_directory":
            path = safe_path(arguments["path"])
            if not path.is_dir():
                return [TextContent(type="text", text=f"Error: {path} is not a directory")]

            items = []
            for item in sorted(path.iterdir()):
                prefix = "[DIR]" if item.is_dir() else "[FILE]"
                items.append(f"{prefix} {item.name}")

            return [TextContent(type="text", text="\n".join(items))]

        elif name == "create_directory":
            path = safe_path(arguments["path"])
            path.mkdir(parents=True, exist_ok=True)
            return [TextContent(type="text", text=f"Created directory {path}")]

        elif name == "search_files":
            path = safe_path(arguments["path"])
            pattern = arguments["pattern"]

            matches = []
            for item in path.rglob(f"*{pattern}*"):
                if is_path_allowed(item):
                    matches.append(str(item))

            result = "\n".join(matches) if matches else "No matches found"
            return [TextContent(type="text", text=result)]

        elif name == "get_file_info":
            path = safe_path(arguments["path"])
            stat = path.stat()

            info = {
                "path": str(path),
                "exists": path.exists(),
                "is_file": path.is_file(),
                "is_directory": path.is_dir(),
                "size_bytes": stat.st_size if path.is_file() else None,
                "modified": stat.st_mtime,
                "created": stat.st_ctime
            }

            return [TextContent(type="text", text=json.dumps(info, indent=2))]

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
