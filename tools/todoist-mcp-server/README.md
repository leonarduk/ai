# Todoist MCP Server

A Model Context Protocol (MCP) server for creating Todoist tasks via email.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Add your Todoist email address to `.env`:
```bash
TODOIST_EMAIL=add.task.5646041.153283871.72694644d659691e@todoist.net
```

The server reuses your existing SMTP configuration (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD) from the `.env` file.

## Configuration

Add this to your MCP client configuration (e.g., Claude Desktop `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "todoist": {
      "command": "python",
      "args": ["C:\\Users\\steph\\workspace\\GitHub\\ai\\tools\\todoist-mcp-server\\server.py"]
    }
  }
}
```

## Tools

### create_todoist_task

Create a task in Todoist by sending an email.

**Parameters:**
- `subject` (string, required): Task title (becomes the task name in Todoist)
- `body` (string, optional): Task details/description

## Testing

```bash
python test_server.py
```

## How it works

This server sends emails to your Todoist email address. The email subject becomes the task title, and the body is added as a comment attachment.

### Advanced task formatting in the subject line

You can add dates, labels, priorities, and assignees directly in the subject:

- **Dates**: Use `<date tomorrow>`, `<date 12/22>`, `<date every other day>`, `<date next Friday>`
- **Labels**: Add existing labels with `@work`, `@email`, `@5min`
- **Priority**: Set priority with `p1` (highest), `p2`, or `p3`
- **Assignee**: Assign to collaborators with `+firstname\ lastname` (e.g., `+Amy\ Jones`)

### Examples

| Subject line | Result |
|-------------|--------|
| `Join our next event! <date Friday> p1` | Task with priority 1, dated on Friday |
| `Review quarterly report <date tomorrow> @work p2` | Task dated tomorrow, with @work label and priority 2 |
| `Re: Office supplies @email p3 <date next Wednesday>` | Task dated next Wednesday, with @email label and priority 3 |
| `Team meeting prep <date every Monday> @work p1` | Recurring task every Monday with @work label and priority 1 |
