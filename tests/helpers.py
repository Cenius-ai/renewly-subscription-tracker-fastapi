"""Shared helpers for the Renewly test suite (real HTTP-level form posts)."""

from __future__ import annotations

import re
import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Subscription, User

CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')
MAIN_RE = re.compile(r"<main[^>]*>(.*?)</main>", re.S)
FLASH_RE = re.compile(r'<div class="flash-stack".*?</div>', re.S)

DEMO_EMAIL = "cenius@cenius.ai"
DEMO_PASSWORD = "cenius"
PASSWORD = "sunshine123"


def main_html(response) -> str:
    """The page body only: excludes the palette index and one-shot flash messages."""
    match = MAIN_RE.search(response.text)
    html = match.group(1) if match else response.text
    return FLASH_RE.sub("", html)


def csrf_token(client, path: str = "/login") -> str:
    response = client.get(path)
    assert response.status_code == 200, f"GET {path} returned {response.status_code}"
    match = CSRF_RE.search(response.text)
    assert match, f"no CSRF token found on {path}"
    return match.group(1)


def login(client, email: str = DEMO_EMAIL, password: str = DEMO_PASSWORD):
    token = csrf_token(client, "/login")
    return client.post(
        "/login",
        data={"csrf_token": token, "email": email, "password": password},
        follow_redirects=False,
    )


def logout(client) -> None:
    token = csrf_token(client, "/dashboard")
    client.post("/logout", data={"csrf_token": token}, follow_redirects=False)


def signup(client, email: str | None = None, password: str = PASSWORD):
    email = email or f"auditor-{uuid.uuid4().hex[:10]}@example.com"
    token = csrf_token(client, "/signup")
    response = client.post(
        "/signup",
        data={
            "csrf_token": token,
            "email": email,
            "password": password,
            "confirm_password": password,
        },
        follow_redirects=False,
    )
    return email, response


def subscription_payload(**overrides) -> dict[str, str]:
    payload = {
        "name": "Netflix",
        "category": "Streaming",
        "price": "15.49",
        "currency": "USD",
        "billing_cycle": "monthly",
        "next_renewal_date": (date.today() + timedelta(days=10)).isoformat(),
        "reminder_days": "7",
    }
    payload.update(overrides)
    return payload


def create_subscription(client, **overrides):
    token = csrf_token(client, "/subscriptions/new")
    payload = subscription_payload(**overrides)
    payload["csrf_token"] = token
    return client.post("/subscriptions", data=payload, follow_redirects=False)


def subscription_id(name: str, email: str = DEMO_EMAIL) -> int:
    """Look the row up in the database (the id is not rendered as data)."""
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == email))
        assert user is not None, f"user {email} missing"
        row = session.scalar(
            select(Subscription).where(
                Subscription.user_id == user.id, Subscription.name == name
            )
        )
        assert row is not None, f"subscription {name} missing for {email}"
        return row.id


def subscription_row(name: str, email: str = DEMO_EMAIL) -> dict | None:
    """Plain snapshot of a stored row (no live ORM session escapes the helper)."""
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            return None
        row = session.scalar(
            select(Subscription).where(
                Subscription.user_id == user.id, Subscription.name == name
            )
        )
        if row is None:
            return None
        return {
            "id": row.id,
            "name": row.name,
            "price_cents": row.price_cents,
            "currency": row.currency,
            "status": row.status,
            "billing_cycle": row.billing_cycle,
            "cancelled_at": row.cancelled_at,
            "reminder_days": row.reminder_days,
            "next_renewal_date": row.next_renewal_date,
        }
