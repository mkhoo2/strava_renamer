import os
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path

import requests

API_BASE_URL = "https://www.strava.com/api/v3"
OAUTH_TOKEN_URL = "https://www.strava.com/oauth/token"
REQUEST_TIMEOUT_SECONDS = 15

_token_lock = threading.Lock()


def _required_setting(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not configured")
    return value


def _token_database_path() -> Path:
    configured_path = os.environ.get("STRAVA_TOKEN_DB")
    if configured_path:
        return Path(configured_path).expanduser()
    return Path.home() / ".strava_bot" / "tokens.sqlite3"


def _get_access_token() -> str:
    with _token_lock:
        database_path = _token_database_path()
        database_path.parent.mkdir(parents=True, exist_ok=True)

        with closing(sqlite3.connect(database_path, timeout=10)) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS oauth_tokens (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    access_token TEXT NOT NULL,
                    refresh_token TEXT NOT NULL,
                    expires_at INTEGER NOT NULL
                )
                """
            )
            row = connection.execute(
                "SELECT access_token, refresh_token, expires_at "
                "FROM oauth_tokens WHERE id = 1"
            ).fetchone()

            if row is not None and row[2] > time.time() + 60:
                return row[0]

            refresh_token = (
                row[1] if row is not None else _required_setting("STRAVA_REFRESH_TOKEN")
            )
            response = requests.post(
                OAUTH_TOKEN_URL,
                data={
                    "client_id": _required_setting("STRAVA_CLIENT_ID"),
                    "client_secret": _required_setting("STRAVA_CLIENT_SECRET"),
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            token_data = response.json()
            if not isinstance(token_data, dict):
                raise RuntimeError("Strava returned an invalid token response")

            access_token = token_data.get("access_token")
            updated_refresh_token = token_data.get("refresh_token")
            expires_at = token_data.get("expires_at")
            if (
                not isinstance(access_token, str)
                or not access_token
                or not isinstance(updated_refresh_token, str)
                or not updated_refresh_token
                or not isinstance(expires_at, int)
            ):
                raise RuntimeError("Strava token response is missing required fields")

            with connection:
                connection.execute(
                    """
                    INSERT INTO oauth_tokens
                        (id, access_token, refresh_token, expires_at)
                    VALUES (1, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        access_token = excluded.access_token,
                        refresh_token = excluded.refresh_token,
                        expires_at = excluded.expires_at
                    """,
                    (access_token, updated_refresh_token, expires_at),
                )

            return access_token


def get_activity(activity_id: int) -> dict[str, object]:
    response = requests.get(
        f"{API_BASE_URL}/activities/{activity_id}",
        headers={"Authorization": f"Bearer {_get_access_token()}"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    activity = response.json()
    if not isinstance(activity, dict):
        raise RuntimeError("Strava returned an invalid activity response")
    return activity


def update_activity(activity_id: int, name: str) -> None:
    response = requests.put(
        f"{API_BASE_URL}/activities/{activity_id}",
        headers={"Authorization": f"Bearer {_get_access_token()}"},
        data={"name": name},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()