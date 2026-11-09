"""Password hashing, session CSRF tokens and timing-safe comparisons.

Passwords use stdlib PBKDF2-HMAC-SHA256 with a per-password random salt, stored
as ``pbkdf2_sha256$iterations$salt_hex$hash_hex``. Verification is constant
time and tolerant of malformed stored values (which simply fail).
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 240_000
SALT_BYTES = 16
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
_STORED_RE = re.compile(r"^pbkdf2_sha256\$(\d+)\$([0-9a-f]+)\$([0-9a-f]+)$")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("ascii"), ITERATIONS
    )
    return f"{ALGORITHM}${ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    match = _STORED_RE.match(stored or "")
    if not match:
        return False
    iterations = int(match.group(1))
    salt = match.group(2)
    expected = match.group(3)
    try:
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("ascii"), iterations
        )
    except (ValueError, UnicodeEncodeError):
        return False
    return hmac.compare_digest(digest.hex(), expected)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def tokens_match(expected: str | None, submitted: str | None) -> bool:
    if not expected or not submitted:
        return False
    return hmac.compare_digest(expected, submitted)


def is_valid_email(value: str) -> bool:
    candidate = (value or "").strip()
    return bool(candidate) and len(candidate) <= 254 and bool(_EMAIL_RE.match(candidate))
