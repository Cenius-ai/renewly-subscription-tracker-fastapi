"""Database models: accounts and the subscriptions they track."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

CATEGORIES: tuple[str, ...] = (
    "Streaming",
    "SaaS",
    "Music",
    "Gaming",
    "Fitness",
    "News",
    "Cloud",
    "Other",
)

CURRENCIES: tuple[str, ...] = ("USD", "EUR", "GBP", "CAD", "AUD")

BILLING_CYCLES: tuple[str, ...] = ("weekly", "monthly", "yearly")

REMINDER_DAYS: tuple[int, ...] = (1, 3, 7, 14, 30)

STATUSES: tuple[str, ...] = ("active", "cancelled")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.email}>"


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("price_cents > 0", name="ck_subscriptions_price_positive"),
        CheckConstraint(
            "category IN ('Streaming','SaaS','Music','Gaming','Fitness','News','Cloud','Other')",
            name="ck_subscriptions_category",
        ),
        CheckConstraint(
            "currency IN ('USD','EUR','GBP','CAD','AUD')",
            name="ck_subscriptions_currency",
        ),
        CheckConstraint(
            "billing_cycle IN ('weekly','monthly','yearly')",
            name="ck_subscriptions_cycle",
        ),
        CheckConstraint(
            "reminder_days IN (1,3,7,14,30)", name="ck_subscriptions_reminder_days"
        ),
        CheckConstraint("status IN ('active','cancelled')", name="ck_subscriptions_status"),
        UniqueConstraint("user_id", "name", name="uq_subscriptions_user_name"),
        Index("ix_subscriptions_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False, default="Other")
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    billing_cycle: Mapped[str] = mapped_column(String(10), nullable=False, default="monthly")
    next_renewal_date: Mapped[date] = mapped_column(Date, nullable=False)
    reminder_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="subscriptions")

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Subscription {self.name} {self.status}>"
