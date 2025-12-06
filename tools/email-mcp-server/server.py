#!/usr/bin/env python3
"""
MCP Server for sending emails via SMTP
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
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env()

server = Server("email-server")

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available email tools"""
    return [
        Tool(
            name="send_email",
            description="Send an email via SMTP. Requires SMTP_HOST, SMTP_PORT, SMTP_USER, and SMTP_PASSWORD environment variables.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line"
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content (plain text or HTML)"
                    },
                    "html": {
                        "type": "boolean",
                        "description": "Whether the body is HTML (default: false)",
                        "default": False
                    }
                },
                "required": ["to", "subject", "body"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    if name != "send_email":
        raise ValueError(f"Unknown tool: {name}")
    
    # Get SMTP configuration from environment
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    if not all([smtp_host, smtp_user, smtp_password]):
        raise ValueError("Missing required environment variables: SMTP_HOST, SMTP_USER, SMTP_PASSWORD")
    
    # Extract arguments
    to_addr = arguments["to"]
    subject = arguments["subject"]
    body = arguments["body"]
    is_html = arguments.get("html", False)
    
    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = smtp_user
    msg['To'] = to_addr
    
    # Attach body
    mime_type = 'html' if is_html else 'plain'
    msg.attach(MIMEText(body, mime_type))
    
    # Send email
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        return [TextContent(
            type="text",
            text=f"Email sent successfully to {to_addr}"
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Failed to send email: {str(e)}"
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
