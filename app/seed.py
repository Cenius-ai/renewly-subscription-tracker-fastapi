"""Idempotent demo seed.

Creates the standard demo account (``cenius@cenius.ai`` / ``cenius``) plus the
plan's ``demo@renewly.app`` / ``demo1234`` account, each with realistic
subscriptions. Safe to run on every boot: existing rows are left untouched.

Run standalone with ``python3 -m app.seed`` (it exits; it never serves HTTP).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.models import Subscription, User, utcnow
from app.security import hash_password


@dataclass(frozen=True)
class SeedSubscription:
    name: str
    category: str
    price_cents: int
    currency: str
    billing_cycle: str
    renews_in_days: int
    reminder_days: int
    cancelled_days_ago: int | None = None


@dataclass(frozen=True)
class SeedAccount:
    email: str
    password: str
    subscriptions: tuple[SeedSubscription, ...]


#: The standard preview account: owns enough data for every screen to render.
STANDARD_ACCOUNT = SeedAccount(
    email="cenius@cenius.ai",
    password="cenius",
    subscriptions=(
        SeedSubscription("Netflix", "Streaming", 1549, "USD", "monthly", 3, 7),
        SeedSubscription("Adobe Creative Cloud", "SaaS", 5999, "USD", "monthly", 5, 14),
        SeedSubscription("iCloud+ 2TB", "Cloud", 299, "USD", "monthly", 1, 3),
        SeedSubscription("Nintendo Switch Online", "Gaming", 1999, "USD", "yearly", 2, 7),
        SeedSubscription("PureGym", "Fitness", 2499, "GBP", "monthly", 8, 7),
        SeedSubscription("Spotify Premium", "Music", 1199, "USD", "monthly", 12, 14),
        SeedSubscription("The Athletic", "News", 7199, "USD", "yearly", 20, 30),
        SeedSubscription("Figma Professional", "SaaS", 14400, "USD", "yearly", 45, 30),
        SeedSubscription(
            "Amazon Music Unlimited", "Music", 999, "EUR", "monthly", 25, 7, cancelled_days_ago=41
        ),
        SeedSubscription(
            "Dropbox Plus", "Cloud", 1199, "USD", "monthly", 18, 14, cancelled_days_ago=12
        ),
    ),
)

#: The credentials documented in the approved plan.
PLAN_ACCOUNT = SeedAccount(
    email="demo@renewly.app",
    password="demo1234",
    subscriptions=(
        SeedSubscription("Disney+", "Streaming", 1099, "USD", "monthly", 4, 7),
        SeedSubscription("Notion Plus", "SaaS", 9600, "USD", "yearly", 33, 7),
        SeedSubscription("Headspace", "Fitness", 6999, "USD", "yearly", 9, 30),
        SeedSubscription("The Economist", "News", 14900, "GBP", "yearly", 16, 30),
        SeedSubscription(
            "YouTube Premium", "Streaming", 1399, "USD", "monthly", 21, 7, cancelled_days_ago=6
        ),
    ),
)

SEED_ACCOUNTS = (STANDARD_ACCOUNT, PLAN_ACCOUNT)


def _ensure_account(session: Session, account: SeedAccount) -> User:
    user = session.scalar(select(User).where(User.email == account.email))
    if user is None:
        user = User(email=account.email, password_hash=hash_password(account.password))
        session.add(user)
        session.flush()  # materialise user.id before children reference it
    return user


def _ensure_subscriptions(session: Session, user: User, account: SeedAccount, today: date) -> int:
    created = 0
    existing_names = set(
        session.scalars(
            select(Subscription.name).where(Subscription.user_id == user.id)
        )
    )
    for seed in account.subscriptions:
        if seed.name in existing_names:
            continue
        cancelled = seed.cancelled_days_ago is not None
        session.add(
            Subscription(
                user_id=user.id,
                name=seed.name,
                category=seed.category,
                price_cents=seed.price_cents,
                currency=seed.currency,
                billing_cycle=seed.billing_cycle,
                next_renewal_date=today + timedelta(days=seed.renews_in_days),
                reminder_days=seed.reminder_days,
                status="cancelled" if cancelled else "active",
                cancelled_at=(
                    utcnow() - timedelta(days=seed.cancelled_days_ago)
                    if seed.cancelled_days_ago is not None
                    else None
                ),
            )
        )
        created += 1
    return created


def seed_demo_data(session: Session, today: date | None = None) -> dict[str, int]:
    """Create demo accounts and their subscriptions where missing."""
    today = today or date.today()
    summary: dict[str, int] = {}
    for account in SEED_ACCOUNTS:
        user = _ensure_account(session, account)
        summary[account.email] = _ensure_subscriptions(session, user, account, today)
    session.commit()
    return summary


def main() -> int:
    init_db()
    with SessionLocal() as session:
        summary = seed_demo_data(session)
    for email, created in summary.items():
        print(f"seed: {email} — {created} subscription(s) created")
    print("seed: done (demo login cenius@cenius.ai / cenius)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
