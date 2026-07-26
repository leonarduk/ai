#!/usr/bin/env python3
"""OAuth2 authentication and Gmail API service construction."""
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# gmail.modify covers reading, labeling, and archiving (removing INBOX) but
# not permanent deletion.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def load_credentials(credentials_path: str, token_path: str) -> Credentials:
    """Return valid user credentials, running the interactive OAuth flow
    the first time and refreshing/caching the token on subsequent calls."""
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"Gmail OAuth client secret not found at '{credentials_path}'. "
                    "Download one from Google Cloud Console (APIs & Services > "
                    "Credentials > OAuth client ID > Desktop app) and set "
                    "GMAIL_CREDENTIALS_PATH."
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())

    return creds


def get_gmail_service(credentials_path: str, token_path: str):
    """Build an authorized Gmail API client."""
    creds = load_credentials(credentials_path, token_path)
    return build("gmail", "v1", credentials=creds)
