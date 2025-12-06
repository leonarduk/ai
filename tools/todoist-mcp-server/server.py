#!/usr/bin/env python3
"""
MCP Server for creating Todoist tasks via email
"""
import smtplib
import os
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio

# Load environment variables from .env file
def load_env():
    """Load environment variables from .env file in project root"""
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

server = Server("todoist-server")

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available Todoist tools"""
    return [
        Tool(
            name="create_todoist_task",
            description="Create a task in Todoist by sending an email.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Task title/name"
                    },
                    "description": {
                        "type": "string",
                        "description": "Task details/description (optional)",
                        "default": ""
                    },
                    "date": {
                        "type": "string",
                        "description": "Due date in natural language (e.g., 'tomorrow', 'Friday', '12/22', 'next Monday', 'every other day', 'every last day')",
                        "default": ""
                    },
                    "priority": {
                        "type": "string",
                        "description": "Priority level: 'p1' (highest), 'p2', or 'p3' (lowest)",
                        "enum": ["p1", "p2", "p3", ""],
                        "default": ""
                    },
                    "labels": {
                        "type": "array",
                        "description": "Labels to apply (e.g., ['work', 'email', 'urgent'])",
                        "items": {"type": "string"},
                        "default": []
                    },
                    "assignee": {
                        "type": "string",
                        "description": "Assignee name in format 'firstname lastname' (only works in shared projects)",
                        "default": ""
                    }
                },
                "required": ["title"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    if name != "create_todoist_task":
        raise ValueError(f"Unknown tool: {name}")
    
    # Get SMTP configuration from environment
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    todoist_email = os.getenv("TODOIST_EMAIL")
    
    if not all([smtp_host, smtp_user, smtp_password]):
        raise ValueError("Missing required environment variables: SMTP_HOST, SMTP_USER, SMTP_PASSWORD")
    
    if not todoist_email:
        raise ValueError("Missing TODOIST_EMAIL environment variable")
    
    # Extract arguments
    title = arguments["title"]
    description = arguments.get("description", "")
    date = arguments.get("date", "")
    priority = arguments.get("priority", "")
    labels = arguments.get("labels", [])
    assignee = arguments.get("assignee", "")
    
    # Build subject line with Todoist formatting
    subject_parts = [title]
    
    if date:
        subject_parts.append(f"<date {date}>")
    
    # Always add MCP label, plus any additional labels
    all_labels = ["MCP"] + labels
    for label in all_labels:
        # Ensure label starts with @
        label_formatted = label if label.startswith('@') else f"@{label}"
        subject_parts.append(label_formatted)
    
    if priority:
        subject_parts.append(priority)
    
    if assignee:
        # Format assignee with + prefix and escape spaces
        assignee_formatted = assignee.replace(' ', '\\ ')
        if not assignee_formatted.startswith('+'):
            assignee_formatted = f"+{assignee_formatted}"
        subject_parts.append(assignee_formatted)
    
    subject = " ".join(subject_parts)
    
    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = smtp_user
    msg['To'] = todoist_email
    
    # Attach body if provided
    if description:
        msg.attach(MIMEText(description, 'plain'))
    
    # Send email to Todoist
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        return [TextContent(
            type="text",
            text=f"Task created in Todoist: '{title}'"
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Failed to create Todoist task: {str(e)}"
        )]

async def main():
    """Main entry point"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
