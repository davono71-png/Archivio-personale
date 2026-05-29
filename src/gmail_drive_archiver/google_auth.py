from __future__ import annotations

from pathlib import Path
from typing import Iterable


DEFAULT_SCOPES = (
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive",
)


def authenticate(credentials_path: Path, token_path: Path, scopes: Iterable[str] = DEFAULT_SCOPES):
    """Return OAuth credentials, refreshing or opening a local consent flow as needed."""

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token_path.parent.mkdir(parents=True, exist_ok=True)
    scopes = tuple(scopes)
    credentials = None

    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(str(token_path), scopes)

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    if not credentials or not credentials.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
        credentials = flow.run_local_server(port=0)

    token_path.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


def build_google_service(service_name: str, version: str, credentials):
    """Build a Google API client for a service."""

    from googleapiclient.discovery import build

    return build(service_name, version, credentials=credentials, cache_discovery=False)
