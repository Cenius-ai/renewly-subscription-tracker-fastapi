"""Renewal reminder arithmetic, computed on read (no scheduler needed)."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from app.models import Subscription

#: A renewal further out than this never shows in the "Upcoming renewals" panel.
REMINDER_HORIZON_DAYS = 30


def add_months(start: date, months: int) -> date:
    """Add whole months, clamping the day (31 Jan + 1 month -> 28/29 Feb)."""
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def add_cycle(start: date, billing_cycle: str, periods: int = 1) -> date:
    if billing_cycle == "weekly":
        return start + timedelta(weeks=periods)
    if billing_cycle == "monthly":
        return add_months(start, periods)
    if billing_cycle == "yearly":
        return add_months(start, 12 * periods)
    raise ValueError(f"unknown billing cycle: {billing_cycle!r}")


def roll_forward(next_renewal_date: date, billing_cycle: str, today: date) -> date:
    """Roll a stored renewal date forward until it is not in the past.

    Stored dates can be stale (the app has no background worker rewriting
    them), so the effective charge date is derived on read. A passed charge
    therefore keeps showing up instead of silently disappearing.
    """
    effective = next_renewal_date
    guard = 0
    while effective < today:
        effective = add_cycle(effective, billing_cycle)
        guard += 1
        if guard > 5_000:  # absurd stored value; stop rather than spin
            break
    return effective


def days_until(target: date, today: date) -> int:
    return (target - today).days


def humanise_days(days: int) -> str:
    if days < 0:
        overdue = abs(days)
        return "overdue by 1 day" if overdue == 1 else f"overdue by {overdue} days"
    if days == 0:
        return "today"
    if days == 1:
        return "in 1 day"
    return f"in {days} days"


@dataclass
class UpcomingRenewal:
    subscription: Subscription
    effective_date: date
    days: int
    #: True when the stored renewal date had already passed and was rolled.
    was_overdue: bool

    @property
    def label(self) -> str:
        return humanise_days(self.days)

    @property
    def is_urgent(self) -> bool:
        return self.days <= 3


def upcoming_renewals(
    subscriptions: list[Subscription], today: date
) -> list[UpcomingRenewal]:
    """Active renewals inside their own lead time and within 30 days, soonest first."""
    upcoming: list[UpcomingRenewal] = []
    for sub in subscriptions:
        if sub.status != "active":
            continue
        effective = roll_forward(sub.next_renewal_date, sub.billing_cycle, today)
        days = days_until(effective, today)
        inside_horizon = 0 <= days <= REMINDER_HORIZON_DAYS
        inside_lead_time = days <= sub.reminder_days
        if inside_horizon and inside_lead_time:
            upcoming.append(
                UpcomingRenewal(
                    subscription=sub,
                    effective_date=effective,
                    days=days,
                    was_overdue=sub.next_renewal_date < today,
                )
            )
    upcoming.sort(key=lambda item: (item.days, item.subscription.name.lower()))
    return upcoming
