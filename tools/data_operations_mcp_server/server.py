#!/usr/bin/env python3
"""
MCP Server for data operations (database, datetime, text, encryption)
Provides tools for database queries, date/time manipulation, text processing, and encryption
"""

import asyncio
import base64
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
# from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from mcp.server import Server
from mcp.types import Tool, TextContent

app = Server("data-operations-server")

# Configure allowed directories for SQLite databases
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

def generate_key_from_password(password: str, salt: bytes = None) -> tuple:
    """Generate encryption key from password"""
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # Database tools
        Tool(
            name="sqlite_query",
            description="Execute a SQL query on a SQLite database",
            inputSchema={
                "type": "object",
                "properties": {
                    "db_path": {"type": "string", "description": "Path to SQLite database file"},
                    "query": {"type": "string", "description": "SQL query to execute"},
                    "params": {"type": "array", "description": "Optional query parameters"}
                },
                "required": ["db_path", "query"]
            }
        ),
        Tool(
            name="sqlite_execute",
            description="Execute a SQL statement (INSERT, UPDATE, DELETE) on a SQLite database",
            inputSchema={
                "type": "object",
                "properties": {
                    "db_path": {"type": "string", "description": "Path to SQLite database file"},
                    "statement": {"type": "string", "description": "SQL statement to execute"},
                    "params": {"type": "array", "description": "Optional statement parameters"}
                },
                "required": ["db_path", "statement"]
            }
        ),
        
        # Date/Time tools
        Tool(
            name="datetime_now",
            description="Get current date and time",
            inputSchema={
                "type": "object",
                "properties": {
                    "format": {"type": "string", "description": "Output format (iso, unix, custom strftime)"}
                },
                "required": []
            }
        ),
        Tool(
            name="datetime_parse",
            description="Parse a date/time string",
            inputSchema={
                "type": "object",
                "properties": {
                    "datetime_string": {"type": "string", "description": "Date/time string to parse"},
                    "format": {"type": "string", "description": "Input format (strftime format)"}
                },
                "required": ["datetime_string"]
            }
        ),
        Tool(
            name="datetime_add",
            description="Add/subtract time to a date",
            inputSchema={
                "type": "object",
                "properties": {
                    "datetime_string": {"type": "string", "description": "Starting date/time (ISO format)"},
                    "days": {"type": "integer", "description": "Days to add (negative to subtract)"},
                    "hours": {"type": "integer", "description": "Hours to add"},
                    "minutes": {"type": "integer", "description": "Minutes to add"},
                    "seconds": {"type": "integer", "description": "Seconds to add"}
                },
                "required": ["datetime_string"]
            }
        ),
        Tool(
            name="datetime_diff",
            description="Calculate difference between two dates",
            inputSchema={
                "type": "object",
                "properties": {
                    "datetime1": {"type": "string", "description": "First date/time (ISO format)"},
                    "datetime2": {"type": "string", "description": "Second date/time (ISO format)"}
                },
                "required": ["datetime1", "datetime2"]
            }
        ),
        
        # Text processing tools
        Tool(
            name="text_search",
            description="Search for pattern in text",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to search in"},
                    "pattern": {"type": "string", "description": "Pattern to search for"},
                    "case_sensitive": {"type": "boolean", "description": "Case sensitive search (default: false)"}
                },
                "required": ["text", "pattern"]
            }
        ),
        Tool(
            name="text_replace",
            description="Replace text using pattern",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to process"},
                    "pattern": {"type": "string", "description": "Pattern to replace"},
                    "replacement": {"type": "string", "description": "Replacement text"},
                    "case_sensitive": {"type": "boolean", "description": "Case sensitive (default: false)"}
                },
                "required": ["text", "pattern", "replacement"]
            }
        ),
        Tool(
            name="text_split",
            description="Split text by delimiter",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to split"},
                    "delimiter": {"type": "string", "description": "Delimiter to split on"},
                    "max_splits": {"type": "integer", "description": "Maximum number of splits"}
                },
                "required": ["text", "delimiter"]
            }
        ),
        Tool(
            name="text_regex_match",
            description="Match text using regular expression",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to match against"},
                    "regex": {"type": "string", "description": "Regular expression pattern"}
                },
                "required": ["text", "regex"]
            }
        ),
        
        # Encryption tools
        Tool(
            name="encrypt_text",
            description="Encrypt text using password-based encryption",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to encrypt"},
                    "password": {"type": "string", "description": "Encryption password"}
                },
                "required": ["text", "password"]
            }
        ),
        Tool(
            name="decrypt_text",
            description="Decrypt text using password-based encryption",
            inputSchema={
                "type": "object",
                "properties": {
                    "encrypted_data": {"type": "string", "description": "Encrypted data (base64)"},
                    "password": {"type": "string", "description": "Decryption password"}
                },
                "required": ["encrypted_data", "password"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        # Database operations
        if name == "sqlite_query":
            db_path = safe_path(arguments["db_path"])
            query = arguments["query"]
            params = arguments.get("params", [])
            
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            rows = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            
            result = {
                "rows": rows,
                "row_count": len(rows)
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "sqlite_execute":
            db_path = safe_path(arguments["db_path"])
            statement = arguments["statement"]
            params = arguments.get("params", [])
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(statement, params)
            conn.commit()
            
            result = {
                "success": True,
                "rows_affected": cursor.rowcount,
                "last_row_id": cursor.lastrowid
            }
            
            conn.close()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        # Date/Time operations
        elif name == "datetime_now":
            format_type = arguments.get("format", "iso")
            now = datetime.now()
            
            if format_type == "iso":
                result = {"datetime": now.isoformat()}
            elif format_type == "unix":
                result = {"timestamp": now.timestamp()}
            else:
                result = {"datetime": now.strftime(format_type)}
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "datetime_parse":
            datetime_string = arguments["datetime_string"]
            format_str = arguments.get("format")
            
            if format_str:
                dt = datetime.strptime(datetime_string, format_str)
            else:
                dt = datetime.fromisoformat(datetime_string)
            
            result = {
                "datetime": dt.isoformat(),
                "timestamp": dt.timestamp(),
                "year": dt.year,
                "month": dt.month,
                "day": dt.day,
                "hour": dt.hour,
                "minute": dt.minute,
                "second": dt.second
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "datetime_add":
            datetime_string = arguments["datetime_string"]
            days = arguments.get("days", 0)
            hours = arguments.get("hours", 0)
            minutes = arguments.get("minutes", 0)
            seconds = arguments.get("seconds", 0)
            
            dt = datetime.fromisoformat(datetime_string)
            delta = timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
            new_dt = dt + delta
            
            result = {
                "original": dt.isoformat(),
                "result": new_dt.isoformat(),
                "delta_days": delta.days,
                "delta_seconds": delta.seconds
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "datetime_diff":
            dt1 = datetime.fromisoformat(arguments["datetime1"])
            dt2 = datetime.fromisoformat(arguments["datetime2"])
            
            diff = dt2 - dt1
            
            result = {
                "datetime1": dt1.isoformat(),
                "datetime2": dt2.isoformat(),
                "difference": {
                    "days": diff.days,
                    "seconds": diff.seconds,
                    "total_seconds": diff.total_seconds(),
                    "total_hours": diff.total_seconds() / 3600,
                    "total_minutes": diff.total_seconds() / 60
                }
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        # Text processing operations
        elif name == "text_search":
            text = arguments["text"]
            pattern = arguments["pattern"]
            case_sensitive = arguments.get("case_sensitive", False)
            
            flags = 0 if case_sensitive else re.IGNORECASE
            matches = list(re.finditer(re.escape(pattern), text, flags))
            
            result = {
                "found": len(matches) > 0,
                "count": len(matches),
                "positions": [m.start() for m in matches]
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "text_replace":
            text = arguments["text"]
            pattern = arguments["pattern"]
            replacement = arguments["replacement"]
            case_sensitive = arguments.get("case_sensitive", False)
            
            flags = 0 if case_sensitive else re.IGNORECASE
            result_text = re.sub(re.escape(pattern), replacement, text, flags=flags)
            
            result = {
                "original": text,
                "result": result_text,
                "replacements_made": text.count(pattern) if case_sensitive else text.lower().count(pattern.lower())
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "text_split":
            text = arguments["text"]
            delimiter = arguments["delimiter"]
            max_splits = arguments.get("max_splits", -1)
            
            parts = text.split(delimiter, max_splits)
            
            result = {
                "parts": parts,
                "count": len(parts)
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "text_regex_match":
            text = arguments["text"]
            regex = arguments["regex"]
            
            matches = list(re.finditer(regex, text))
            
            result = {
                "matched": len(matches) > 0,
                "matches": [
                    {
                        "text": m.group(),
                        "start": m.start(),
                        "end": m.end(),
                        "groups": m.groups()
                    }
                    for m in matches
                ]
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        # Encryption operations
        elif name == "encrypt_text":
            text = arguments["text"]
            password = arguments["password"]
            
            key, salt = generate_key_from_password(password)
            cipher = Fernet(key)
            
            encrypted = cipher.encrypt(text.encode())
            
            # Combine salt and encrypted data
            combined = base64.b64encode(salt + encrypted).decode()
            
            result = {
                "encrypted_data": combined,
                "note": "Store this encrypted data safely. You'll need the same password to decrypt."
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "decrypt_text":
            encrypted_data = arguments["encrypted_data"]
            password = arguments["password"]
            
            # Decode and split salt and encrypted data
            combined = base64.b64decode(encrypted_data)
            salt = combined[:16]
            encrypted = combined[16:]
            
            key, _ = generate_key_from_password(password, salt)
            cipher = Fernet(key)
            
            decrypted = cipher.decrypt(encrypted).decode()
            
            result = {
                "decrypted_text": decrypted
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
