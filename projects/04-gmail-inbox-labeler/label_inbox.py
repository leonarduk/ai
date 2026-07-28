#!/usr/bin/env python3
"""Move Gmail inbox messages into one or more chosen labels, classified by a
local Ollama model.

Usage:
    python label_inbox.py --dry-run
    python label_inbox.py --max-results 50
"""
import argparse
import logging
import os
from pathlib import Path

from gmail_auth import get_gmail_service
from ollama_classifier import (
    DEFAULT_HOST,
    DEFAULT_MODEL,
    OllamaConnectionError,
    classify_email,
)

logger = logging.getLogger("label_inbox")


def load_env():
    """Load environment variables from a .env file next to this script."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def get_user_labels(service) -> dict:
    """Return {label_name: label_id} for the user's own (non-system) labels."""
    response = service.users().labels().list(userId="me").execute()
    return {
        label["name"]: label["id"]
        for label in response.get("labels", [])
        if label.get("type") == "user"
    }


def get_message_summary(service, message_id: str) -> dict:
    """Fetch just the headers/snippet needed for classification."""
    message = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["From", "Subject"],
        )
        .execute()
    )
    headers = {h["name"]: h["value"] for h in message["payload"].get("headers", [])}
    return {
        "id": message_id,
        "subject": headers.get("Subject", "(no subject)"),
        "sender": headers.get("From", "(unknown sender)"),
        "snippet": message.get("snippet", ""),
    }


def list_inbox_message_ids(service, query: str, max_results: int) -> list[str]:
    ids = []
    request = service.users().messages().list(
        userId="me", q=query, maxResults=min(max_results, 500)
    )
    while request is not None and len(ids) < max_results:
        response = request.execute()
        ids.extend(m["id"] for m in response.get("messages", []))
        request = service.users().messages().list_next(request, response)
    return ids[:max_results]


def apply_labels(service, message_id: str, label_ids: list[str]) -> None:
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"addLabelIds": label_ids, "removeLabelIds": ["INBOX"]},
    ).execute()


def run(
    query: str,
    max_results: int,
    dry_run: bool,
    model: str,
    ollama_host: str,
    credentials_path: str,
    token_path: str,
    target_labels: list[str] | None = None,
) -> None:
    service = get_gmail_service(credentials_path, token_path)

    label_name_to_id = get_user_labels(service)
    if not label_name_to_id:
        logger.warning("No user labels found in this Gmail account. Nothing to classify into.")
        return

    if target_labels:
        lookup = {name.lower(): name for name in label_name_to_id}
        label_names = []
        for wanted in target_labels:
            match = lookup.get(wanted.strip().lower())
            if not match:
                logger.warning("Requested label '%s' not found in Gmail account; ignoring.", wanted)
                continue
            label_names.append(match)
        if not label_names:
            logger.error("None of the requested --labels matched an existing Gmail label. Aborting.")
            return
    else:
        label_names = list(label_name_to_id.keys())

    message_ids = list_inbox_message_ids(service, query, max_results)
    logger.info("Found %d inbox message(s) matching query '%s'", len(message_ids), query)

    for message_id in message_ids:
        summary = get_message_summary(service, message_id)

        try:
            chosen_labels = classify_email(
                subject=summary["subject"],
                sender=summary["sender"],
                snippet=summary["snippet"],
                labels=label_names,
                model=model,
                host=ollama_host,
            )
        except OllamaConnectionError as exc:
            logger.error("Skipping message %s: %s", message_id, exc)
            continue

        if not chosen_labels:
            logger.info(
                "SKIP  %s | %s -> no matching label, left in inbox",
                message_id,
                summary["subject"],
            )
            continue

        label_ids = [label_name_to_id[name] for name in chosen_labels]

        if dry_run:
            logger.info(
                "DRY-RUN  %s | %s -> would apply %s and remove from inbox",
                message_id,
                summary["subject"],
                chosen_labels,
            )
        else:
            apply_labels(service, message_id, label_ids)
            logger.info(
                "MOVED  %s | %s -> %s",
                message_id,
                summary["subject"],
                chosen_labels,
            )


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--query",
        default="in:inbox",
        help="Gmail search query selecting which messages to process (default: in:inbox)",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=100,
        help="Maximum number of messages to process in one run (default: 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log the label decisions without modifying any message",
    )
    parser.add_argument(
        "--labels",
        default=os.getenv("GMAIL_TARGET_LABELS", ""),
        help=(
            "Comma-separated list of existing Gmail labels to restrict classification to "
            "(e.g. 'Finances/Job Hunt'). If omitted, every user label in the account is "
            "offered to the model as a candidate."
        ),
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OLLAMA_MODEL", DEFAULT_MODEL),
        help="Local Ollama model to use for classification",
    )
    parser.add_argument(
        "--ollama-host",
        default=os.getenv("OLLAMA_HOST", DEFAULT_HOST),
        help="Local Ollama server URL",
    )
    parser.add_argument(
        "--credentials",
        default=os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json"),
        help="Path to the Gmail OAuth client secret JSON",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("GMAIL_TOKEN_PATH", "token.json"),
        help="Path where the authorized user token is cached",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


def main(argv=None) -> None:
    load_env()
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    target_labels = [name for name in args.labels.split(",") if name.strip()]
    run(
        query=args.query,
        max_results=args.max_results,
        dry_run=args.dry_run,
        model=args.model,
        ollama_host=args.ollama_host,
        credentials_path=args.credentials,
        token_path=args.token,
        target_labels=target_labels or None,
    )


if __name__ == "__main__":
    main()
