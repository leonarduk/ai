#!/usr/bin/env python3
"""
Entry submission logic for the prize draw MCP server.

Deliberately contains no LLM/provider logic - the orchestrating client
(issue #23) resolves what values go into each field; this module just
performs (or dry-runs) the mechanical act of submitting them, and enforces
the safety rules from issue #22:

- refuse to submit personal/financial data without an explicit confirmation
  flag from the caller
- refuse to proceed for draws that require a purchase unless explicitly
  overridden
- support a dry-run mode that logs what would be submitted without
  submitting anything
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import requests

REQUEST_TIMEOUT_SECONDS = 10

# Field names that must never be sent without `confirm_personal_data=True`.
# Matching is case-insensitive and by substring, so e.g. "billing_address"
# and "cardNumber" are both caught.
PERSONAL_FIELD_MARKERS = (
    "email",
    "name",
    "address",
    "phone",
    "mobile",
    "postcode",
    "zip",
    "dob",
    "birth",
    "card",
    "cvv",
    "sort_code",
    "sortcode",
    "account_number",
    "iban",
    "password",
    "ssn",
    "national_insurance",
)

VALID_ENTRY_METHODS = {"web_form", "email", "social"}


class EntryRejected(Exception):
    """Raised when submit_entry refuses to proceed for a safety reason."""


def find_personal_fields(fields: dict) -> list[str]:
    """Return the subset of field names that look like personal/financial data."""
    flagged = []
    for key in fields:
        lowered = key.lower()
        if any(marker in lowered for marker in PERSONAL_FIELD_MARKERS):
            flagged.append(key)
    return flagged


def guard_submission(
    *,
    requires_purchase: bool,
    confirm_purchase_required: bool,
    fields: dict,
    confirm_personal_data: bool,
) -> None:
    """Raise EntryRejected if the submission violates a safety rule.

    Purchase requirement and personal-data checks are independent: both are
    evaluated so the caller gets a single combined error rather than having
    to fix one and re-discover the other.
    """
    reasons = []
    if requires_purchase and not confirm_purchase_required:
        reasons.append(
            "This draw requires a purchase to enter; refusing unless "
            "confirm_purchase_required=true is explicitly set."
        )
    personal_fields = find_personal_fields(fields)
    if personal_fields and not confirm_personal_data:
        reasons.append(
            "Fields look like personal/financial data "
            f"({', '.join(sorted(personal_fields))}); refusing unless "
            "confirm_personal_data=true is explicitly set."
        )
    if reasons:
        raise EntryRejected(" ".join(reasons))


def submit_web_form(
    url: str, fields: dict, session: Optional[requests.Session] = None
) -> dict:
    """POST field values to a web entry form and return a result summary."""
    http = session or requests
    response = http.post(url, data=fields, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return {"method": "web_form", "url": url, "status_code": response.status_code}


def submit_email(
    *,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    to_addr: str,
    subject: str,
    body: str,
    smtp_client: Optional[type] = None,
) -> dict:
    """Send an email entry via SMTP and return a result summary."""
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = smtp_user
    message["To"] = to_addr
    message.attach(MIMEText(body, "plain"))

    client_cls = smtp_client or smtplib.SMTP
    with client_cls(smtp_host, smtp_port) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(message)
    return {"method": "email", "to": to_addr, "subject": subject}


def submit_social(action: str, target_url: str, fields: dict) -> dict:
    """Record a simple social entry action (follow/like/retweet/etc).

    There is no generic, credential-free social API to call here - each
    platform needs its own OAuth app and is explicitly out of scope for this
    issue (see #21). This performs no network call; it returns a
    "simulated" result so the caller/log can still track that the action was
    requested, without silently pretending a real API call happened.
    """
    return {
        "method": "social",
        "action": action,
        "target_url": target_url,
        "simulated": True,
        "note": (
            "Social actions are not wired to a live provider API in this "
            "server; the action was recorded but not actually performed."
        ),
        "fields": fields,
    }
