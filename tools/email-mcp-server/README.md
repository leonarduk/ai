# Email MCP Server

A Model Context Protocol (MCP) server for sending emails via SMTP and creating Todoist tasks.

## Features

- **send_email**: Send emails via SMTP with plain text or HTML content
- **create_todoist_task**: Create Todoist tasks with due dates, priorities, labels, and assignees

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Add environment variables to your `.env` file:
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
TODOIST_EMAIL=your-unique-todoist-email@todoist.com
```

For Gmail, you'll need to use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password.

For Todoist, get your unique email address from: Settings > Integration > Email

## Tools

### send_email

Send an email via SMTP.

**Parameters:**
- `to` (string, required): Recipient email address
- `subject` (string, required): Email subject line
- `body` (string, required): Email body content
- `html` (boolean, optional): Whether the body is HTML (default: false)

**Example:**
```json
{
  "to": "recipient@example.com",
  "subject": "Hello",
  "body": "This is a test email"
}
```

### create_todoist_task

Create a task in Todoist by sending an email with special formatting.

**Parameters:**
- `title` (string, required): Task title/name
- `description` (string, optional): Task details/description
- `date` (string, optional): Due date in natural language (e.g., "tomorrow", "Friday", "12/22", "next Monday", "every other day")
- `priority` (string, optional): Priority level: "p1" (highest), "p2", or "p3" (lowest)
- `labels` (array, optional): Labels to apply (e.g., ["work", "email", "urgent"])
- `assignee` (string, optional): Assignee name in format "firstname lastname" (only works in shared projects)

**Example:**
```json
{
  "title": "Review pull request",
  "description": "Check the new authentication module PR",
  "date": "tomorrow at 2pm",
  "priority": "p1",
  "labels": ["code-review", "urgent"]
}
```

**Note:** All tasks created through this server automatically get the "MCP" label for easy filtering.

## Todoist Email Formatting

The server automatically formats the email subject line according to Todoist's requirements:
- Date: `<date tomorrow>` 
- Labels: `@work @urgent`
- Priority: `p1`, `p2`, or `p3`
- Assignee: `+John\ Doe` (spaces escaped with backslash)

## Testing

You can test the server directly:

```bash
python server.py
```

Then send MCP protocol messages via stdin/stdout.
