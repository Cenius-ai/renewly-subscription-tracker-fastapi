"""Small in-process login throttle (single instance, windowed, memory bounded).

Only failed password attempts are counted, so a busy but successful user is
never locked out. State is per process, which is correct for the single
instance this app is designed to run as.
"""

from __future__ import annotations

import time
from collections import deque

from app.config import settings

WINDOW_SECONDS = 300
MAX_FAILURES = 10
_MAX_TRACKED_KEYS = 5_000

_failures: dict[str, deque[float]] = {}


def _prune(bucket: deque[float], now: float) -> None:
    while bucket and now - bucket[0] > WINDOW_SECONDS:
        bucket.popleft()


def is_locked(key: str) -> bool:
    if not settings.rate_limit_enabled:
        return False
    bucket = _failures.get(key)
    if not bucket:
        return False
    _prune(bucket, time.monotonic())
    return len(bucket) >= MAX_FAILURES


def record_failure(key: str) -> None:
    if not settings.rate_limit_enabled:
        return
    if len(_failures) > _MAX_TRACKED_KEYS:
        _failures.clear()
    bucket = _failures.setdefault(key, deque())
    _prune(bucket, time.monotonic())
    bucket.append(time.monotonic())


def clear_failures(key: str) -> None:
    _failures.pop(key, None)


def reset_all() -> None:
    """Test hook."""
    _failures.clear()
