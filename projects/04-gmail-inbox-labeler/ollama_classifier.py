#!/usr/bin/env python3
"""Classify an email into zero or more existing Gmail labels using a local
Ollama model. No email content is ever sent to a hosted/cloud LLM."""
import json

import requests

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3"
DEFAULT_TIMEOUT = 60

_PROMPT_TEMPLATE = """You are an email triage assistant. Choose which of the
following labels this email belongs to. You may choose zero, one, or several
labels. Only choose from the exact label names listed below - never invent a
new label.

Available labels:
{labels}

Email:
From: {sender}
Subject: {subject}
Snippet: {snippet}
"""


class OllamaConnectionError(RuntimeError):
    """Raised when the local Ollama server can't be reached."""


def _build_prompt(subject: str, sender: str, snippet: str, labels: list[str]) -> str:
    label_list = "\n".join(f"- {label}" for label in labels)
    return _PROMPT_TEMPLATE.format(
        labels=label_list, sender=sender, subject=subject, snippet=snippet
    )


def _response_schema(valid_labels: list[str]) -> dict:
    """Ollama structured-output schema constraining the model to a JSON
    object of the form {"labels": [...]}, with each item restricted to one
    of the account's real label names. Plain `format: "json"` only
    guarantees *some* JSON object back (e.g. {"Work": true}), not this
    shape, so the schema is required for reliable parsing."""
    return {
        "type": "object",
        "properties": {
            "labels": {
                "type": "array",
                "items": {"type": "string", "enum": valid_labels},
            }
        },
        "required": ["labels"],
    }


def _parse_labels(raw_text: str, valid_labels: list[str]) -> list[str]:
    """Parse the model's {"labels": [...]} response and keep only labels
    that exactly match (case-insensitively) one of the known valid labels."""
    lookup = {label.lower(): label for label in valid_labels}
    try:
        parsed = json.loads(raw_text.strip())
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, dict):
        return []

    items = parsed.get("labels")
    if not isinstance(items, list):
        return []

    chosen = []
    for item in items:
        if not isinstance(item, str):
            continue
        match = lookup.get(item.strip().lower())
        if match and match not in chosen:
            chosen.append(match)
    return chosen


def classify_email(
    subject: str,
    sender: str,
    snippet: str,
    labels: list[str],
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[str]:
    """Return the subset of `labels` the local Ollama model assigns to this
    email. Returns an empty list if no label applies."""
    if not labels:
        return []

    prompt = _build_prompt(subject, sender, snippet, labels)

    try:
        response = requests.post(
            f"{host.rstrip('/')}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": _response_schema(labels),
            },
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError as exc:
        raise OllamaConnectionError(
            f"Could not reach local Ollama server at {host}. "
            "Is `ollama serve` running?"
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise OllamaConnectionError(f"Ollama request failed: {exc}") from exc

    raw_text = response.json().get("response", "")
    return _parse_labels(raw_text, labels)
