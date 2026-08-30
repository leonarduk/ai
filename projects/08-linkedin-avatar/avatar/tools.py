"""record_contact, record_unknown_question, lookup_project.

Three tools for the DeepSeek tool-use loop (avatar/llm.py). Two send a Pushover
notification, one reads github.json locally. None of them may raise — a failed
notification or an unknown project name must degrade to an error result, never
take down the chat turn. See docs/design.md §5.
"""

import difflib
import json
import logging
import os
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

PUSHOVER_URL = "https://api.pushover.net/1/messages.json"
GITHUB_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent.parent / "knowledge" / "github.json"
)

RECORD_CONTACT = "record_contact"
RECORD_UNKNOWN_QUESTION = "record_unknown_question"
LOOKUP_PROJECT = "lookup_project"

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": RECORD_CONTACT,
            "description": (
                "Record that a visitor wants to be contacted. Sends a push "
                "notification with their details; call this whenever a visitor "
                "gives an email address or asks to be put in touch."
            ),
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "The visitor's email address.",
                    },
                    "name": {
                        "type": ["string", "null"],
                        "description": "The visitor's name, if given.",
                    },
                    "notes": {
                        "type": ["string", "null"],
                        "description": "Anything relevant about why they want to talk.",
                    },
                },
                "required": ["email", "name", "notes"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": RECORD_UNKNOWN_QUESTION,
            "description": (
                "Record a question that could not be answered from the available "
                "knowledge. Call this instead of guessing whenever you don't know "
                "the answer — never invent an answer about Steve's experience."
            ),
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The visitor's question, verbatim.",
                    },
                },
                "required": ["question"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": LOOKUP_PROJECT,
            "description": (
                "Fetch the full record for one GitHub repo — description, "
                "languages, README excerpt and any curated note. Use this when "
                "the conversation goes into detail on a specific project named "
                "in the GitHub index."
            ),
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The repo name, as it appears in the GitHub index.",
                    },
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
]


def _pushover_notify(title, message):
    """POST a Pushover notification. Never raises — logs and returns a status dict."""
    user = os.environ.get("PUSHOVER_USER")
    token = os.environ.get("PUSHOVER_TOKEN")

    if not user or not token:
        logger.info("Pushover not configured; logging instead. %s: %s", title, message)
        return {"status": "logged", "detail": "PUSHOVER_USER/PUSHOVER_TOKEN not set"}

    try:
        response = requests.post(
            PUSHOVER_URL,
            data={"token": token, "user": user, "title": title, "message": message},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Pushover notification failed: %s", title)
        return {"status": "failed", "detail": "notification could not be sent"}

    return {"status": "sent"}


def record_contact(email, name=None, notes=None):
    """Notify me that a visitor wants to be contacted."""
    lines = [f"Email: {email}"]
    if name:
        lines.append(f"Name: {name}")
    if notes:
        lines.append(f"Notes: {notes}")
    result = _pushover_notify("LinkedIn Avatar: contact request", "\n".join(lines))
    return {"recorded": result["status"] in ("sent", "logged"), **result}


def record_unknown_question(question):
    """Notify me that the avatar didn't know the answer to something."""
    result = _pushover_notify("LinkedIn Avatar: unknown question", question)
    return {"recorded": result["status"] in ("sent", "logged"), **result}


def lookup_project(name):
    """Fetch the full github.json record for one repo, fuzzy-matching the name."""
    try:
        raw = GITHUB_SNAPSHOT_PATH.read_text(encoding="utf-8")
        records = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        logger.exception("Could not read GitHub snapshot at %s", GITHUB_SNAPSHOT_PATH)
        return {
            "found": False,
            "message": "the GitHub project index is unavailable right now",
        }

    by_name = {record["name"].lower(): record for record in records}
    query = name.strip().lower()

    if query in by_name:
        return {"found": True, "project": by_name[query]}

    matches = difflib.get_close_matches(query, by_name.keys(), n=1, cutoff=0.6)
    if matches:
        return {"found": True, "project": by_name[matches[0]]}

    return {"found": False, "message": f"no project matching '{name}' was found"}


_DISPATCH_TABLE = {
    RECORD_CONTACT: record_contact,
    RECORD_UNKNOWN_QUESTION: record_unknown_question,
    LOOKUP_PROJECT: lookup_project,
}


def dispatch(name, arguments):
    """Call a tool by name with keyword arguments. Never raises."""
    handler = _DISPATCH_TABLE.get(name)
    if handler is None:
        return {"error": f"unknown tool: {name}"}

    try:
        return handler(**arguments)
    except TypeError:
        logger.exception("Bad arguments for tool %s: %r", name, arguments)
        return {"error": f"invalid arguments for tool: {name}"}
