"""Runtime configuration.

Every value has a working default so a fresh clone boots with no ``.env`` file.
A local ``.env`` next to this package is read (without overriding real
environment variables) so self-hosters can configure the app the usual way.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Development fallback for the session-signing key. It is intentionally a
# documented, non-production value: the app must boot on a clean clone with no
# environment at all. ``install.sh`` generates a unique key into ``.env`` for
# real deployments, and any ``SECRET_KEY`` in the environment wins.
DEV_SECRET_KEY = "cenius-dev-4d9e7b1a62c8f530"

DEFAULT_DATABASE_URL = "sqlite:///./renewly.db"


def _load_dotenv(path: Path) -> None:
    """Minimal ``KEY=VALUE`` reader; real environment variables win."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv(BASE_DIR / ".env")


class Settings:
    """Plain settings object; no required fields, no import-time failures."""

    def __init__(self) -> None:
        self.secret_key = os.getenv("SECRET_KEY") or DEV_SECRET_KEY
        self.database_url = os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL
        self.session_cookie = "renewly_session"
        self.session_max_age = 60 * 60 * 24 * 14  # 14 days
        self.app_name = "Renewly"
        # Login throttling can be switched off for test runs.
        self.rate_limit_enabled = os.getenv("RENEWLY_RATE_LIMIT", "on").lower() not in {
            "off",
            "false",
            "0",
            "no",
        }

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


settings = Settings()
