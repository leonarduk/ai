# Email MCP Server

A Model Context Protocol (MCP) server for sending emails via SMTP.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables for your SMTP configuration:
```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
```

For Gmail, you'll need to use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password.

## Configuration

Add this to your MCP client configuration (e.g., Claude Desktop `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "email": {
      "command": "python",
      "args": ["C:\\Users\\steph\\workspace\\GitHub\\ai\\tools\\email-mcp-server\\server.py"],
      "env": {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "your-email@gmail.com",
        "SMTP_PASSWORD": "your-app-password"
      }
    }
  }
}
```

## Tools

### send_email

Send an email via SMTP.

**Parameters:**
- `to` (string, required): Recipient email address
- `subject` (string, required): Email subject line
- `body` (string, required): Email body content
- `html` (boolean, optional): Whether the body is HTML (default: false)

## Testing

You can test the server directly:

```bash
python server.py
```

Then send MCP protocol messages via stdin/stdout.
