#!/usr/bin/env python3
"""
MCP Server for file processing operations (CSV, Excel, compression)
Provides tools for reading/writing CSV and Excel files, and file compression
"""

import asyncio
import json
import os
import csv
import zipfile
import gzip
import shutil
from pathlib import Path
from typing import Optional
from io import StringIO
from mcp.server import Server
from mcp.types import Tool, TextContent
import pandas as pd

app = Server("file-processing-server")

# Configure allowed directories
ALLOWED_DIRS = [
    Path(r"C:\Users\steph\workspace")
]

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

def is_path_allowed(path: Path) -> bool:
    """Check if path is within allowed directories"""
    try:
        resolved = path.resolve()
        return any(resolved.is_relative_to(allowed) for allowed in ALLOWED_DIRS)
    except (ValueError, OSError):
        return False

def safe_path(path_str: str) -> Path:
    """Convert string to Path and validate it's allowed"""
    path = Path(path_str)
    if is_path_allowed(path):
        return path
    raise ValueError(f"Access denied: {path_str} is outside allowed directories")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="csv_read",
            description="Read a CSV file and return its contents",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the CSV file"},
                    "delimiter": {"type": "string", "description": "Delimiter character (default: ',')"},
                    "has_header": {"type": "boolean", "description": "Whether file has header row (default: true)"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="csv_write",
            description="Write data to a CSV file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the CSV file"},
                    "data": {"type": "array", "description": "Array of arrays representing rows"},
                    "delimiter": {"type": "string", "description": "Delimiter character (default: ',')"},
                    "header": {"type": "array", "description": "Optional header row"}
                },
                "required": ["path", "data"]
            }
        ),
        Tool(
            name="excel_read",
            description="Read an Excel file and return its contents",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the Excel file"},
                    "sheet_name": {"type": "string", "description": "Sheet name to read (default: first sheet)"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="excel_write",
            description="Write data to an Excel file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the Excel file"},
                    "data": {"type": "array", "description": "Array of arrays representing rows"},
                    "sheet_name": {"type": "string", "description": "Sheet name (default: 'Sheet1')"},
                    "header": {"type": "array", "description": "Optional header row"}
                },
                "required": ["path", "data"]
            }
        ),
        Tool(
            name="zip_compress",
            description="Compress files or directories into a ZIP archive",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_paths": {"type": "array", "description": "List of file/directory paths to compress"},
                    "output_path": {"type": "string", "description": "Path for the output ZIP file"}
                },
                "required": ["source_paths", "output_path"]
            }
        ),
        Tool(
            name="zip_decompress",
            description="Extract files from a ZIP archive",
            inputSchema={
                "type": "object",
                "properties": {
                    "zip_path": {"type": "string", "description": "Path to the ZIP file"},
                    "output_dir": {"type": "string", "description": "Directory to extract files to"}
                },
                "required": ["zip_path", "output_dir"]
            }
        ),
        Tool(
            name="gzip_compress",
            description="Compress a file using GZIP",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_path": {"type": "string", "description": "Path to the file to compress"},
                    "output_path": {"type": "string", "description": "Path for the output .gz file"}
                },
                "required": ["source_path", "output_path"]
            }
        ),
        Tool(
            name="gzip_decompress",
            description="Decompress a GZIP file",
            inputSchema={
                "type": "object",
                "properties": {
                    "gzip_path": {"type": "string", "description": "Path to the .gz file"},
                    "output_path": {"type": "string", "description": "Path for the decompressed file"}
                },
                "required": ["gzip_path", "output_path"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "csv_read":
            path = safe_path(arguments["path"])
            delimiter = arguments.get("delimiter", ",")
            has_header = arguments.get("has_header", True)
            
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=delimiter)
                rows = list(reader)
            
            result = {
                "rows": rows,
                "row_count": len(rows),
                "column_count": len(rows[0]) if rows else 0
            }
            
            if has_header and rows:
                result["header"] = rows[0]
                result["data"] = rows[1:]
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "csv_write":
            path = safe_path(arguments["path"])
            data = arguments["data"]
            delimiter = arguments.get("delimiter", ",")
            header = arguments.get("header")
            
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=delimiter)
                if header:
                    writer.writerow(header)
                writer.writerows(data)
            
            result = {
                "success": True,
                "path": str(path),
                "rows_written": len(data) + (1 if header else 0)
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "excel_read":
            path = safe_path(arguments["path"])
            sheet_name = arguments.get("sheet_name", 0)
            
            df = pd.read_excel(path, sheet_name=sheet_name)
            
            result = {
                "columns": df.columns.tolist(),
                "data": df.values.tolist(),
                "shape": df.shape,
                "row_count": len(df),
                "column_count": len(df.columns)
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "excel_write":
            path = safe_path(arguments["path"])
            data = arguments["data"]
            sheet_name = arguments.get("sheet_name", "Sheet1")
            header = arguments.get("header")
            
            path.parent.mkdir(parents=True, exist_ok=True)
            
            if header:
                df = pd.DataFrame(data, columns=header)
            else:
                df = pd.DataFrame(data)
            
            df.to_excel(path, sheet_name=sheet_name, index=False)
            
            result = {
                "success": True,
                "path": str(path),
                "rows_written": len(df),
                "columns_written": len(df.columns)
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "zip_compress":
            source_paths = [safe_path(p) for p in arguments["source_paths"]]
            output_path = safe_path(arguments["output_path"])
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for source in source_paths:
                    if source.is_file():
                        zipf.write(source, source.name)
                    elif source.is_dir():
                        for file_path in source.rglob('*'):
                            if file_path.is_file():
                                arcname = file_path.relative_to(source.parent)
                                zipf.write(file_path, arcname)
            
            result = {
                "success": True,
                "output_path": str(output_path),
                "compressed_size": output_path.stat().st_size
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "zip_decompress":
            zip_path = safe_path(arguments["zip_path"])
            output_dir = safe_path(arguments["output_dir"])
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                zipf.extractall(output_dir)
                file_list = zipf.namelist()
            
            result = {
                "success": True,
                "output_dir": str(output_dir),
                "files_extracted": len(file_list),
                "file_list": file_list
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "gzip_compress":
            source_path = safe_path(arguments["source_path"])
            output_path = safe_path(arguments["output_path"])
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(source_path, 'rb') as f_in:
                with gzip.open(output_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            result = {
                "success": True,
                "output_path": str(output_path),
                "original_size": source_path.stat().st_size,
                "compressed_size": output_path.stat().st_size
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "gzip_decompress":
            gzip_path = safe_path(arguments["gzip_path"])
            output_path = safe_path(arguments["output_path"])
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with gzip.open(gzip_path, 'rb') as f_in:
                with open(output_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            result = {
                "success": True,
                "output_path": str(output_path),
                "decompressed_size": output_path.stat().st_size
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
