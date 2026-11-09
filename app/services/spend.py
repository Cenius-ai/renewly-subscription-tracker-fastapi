"""Subscription cost arithmetic: money stays in integer minor units (cents)."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.models import Subscription

CYCLE_UNIT = {"weekly": "week", "monthly": "month", "yearly": "year"}

#: Upper bound for a single subscription price: 1,000,000.00 in any currency.
#: Keeps cent conversion far away from integer overflow.
MAX_PRICE_CENTS = 100_000_000


def _round_half_up(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def monthly_cents(price_cents: int, billing_cycle: str) -> int:
    """Normalise a price to a monthly amount in cents."""
    if billing_cycle == "monthly":
        return price_cents
    if billing_cycle == "yearly":
        return _round_half_up(Decimal(price_cents) / Decimal(12))
    if billing_cycle == "weekly":
        return _round_half_up(Decimal(price_cents) * Decimal(52) / Decimal(12))
    raise ValueError(f"unknown billing cycle: {billing_cycle!r}")


def yearly_cents(price_cents: int, billing_cycle: str) -> int:
    """Normalise a price to a yearly amount in cents."""
    if billing_cycle == "yearly":
        return price_cents
    if billing_cycle == "monthly":
        return price_cents * 12
    if billing_cycle == "weekly":
        return price_cents * 52
    raise ValueError(f"unknown billing cycle: {billing_cycle!r}")


def format_cents(amount_cents: int) -> str:
    """Render cents as a grouped decimal string, e.g. ``1,234.50``."""
    value = (Decimal(int(amount_cents)) / Decimal(100)).quantize(Decimal("0.01"))
    return f"{value:,.2f}"


@dataclass
class CurrencyTotal:
    currency: str
    monthly_cents: int = 0
    yearly_cents: int = 0


@dataclass
class CategoryBreakdown:
    category: str
    #: currency -> {"monthly": cents, "yearly": cents}
    amounts: dict[str, dict[str, int]] = field(default_factory=dict)


def _sorted_currencies(currencies: set[str]) -> list[str]:
    return sorted(currencies)


def active_totals(subscriptions: list[Subscription]) -> OrderedDict[str, CurrencyTotal]:
    """Monthly/yearly spend of active subscriptions, grouped per currency."""
    totals: dict[str, CurrencyTotal] = {}
    for sub in subscriptions:
        if sub.status != "active":
            continue
        bucket = totals.setdefault(sub.currency, CurrencyTotal(sub.currency))
        bucket.monthly_cents += monthly_cents(sub.price_cents, sub.billing_cycle)
        bucket.yearly_cents += yearly_cents(sub.price_cents, sub.billing_cycle)
    return OrderedDict((currency, totals[currency]) for currency in _sorted_currencies(set(totals)))


def savings_totals(subscriptions: list[Subscription]) -> OrderedDict[str, CurrencyTotal]:
    """Normalised cost of cancelled subscriptions, grouped per currency."""
    totals: dict[str, CurrencyTotal] = {}
    for sub in subscriptions:
        if sub.status != "cancelled":
            continue
        bucket = totals.setdefault(sub.currency, CurrencyTotal(sub.currency))
        bucket.monthly_cents += monthly_cents(sub.price_cents, sub.billing_cycle)
        bucket.yearly_cents += yearly_cents(sub.price_cents, sub.billing_cycle)
    return OrderedDict((currency, totals[currency]) for currency in _sorted_currencies(set(totals)))


def currencies_in_use(subscriptions: list[Subscription]) -> list[str]:
    return _sorted_currencies({sub.currency for sub in subscriptions if sub.status == "active"})


def category_breakdown(
    subscriptions: list[Subscription], currencies: list[str]
) -> list[CategoryBreakdown]:
    """Active spend per category, one monthly/yearly column per currency in use."""
    rows: dict[str, CategoryBreakdown] = {}
    for sub in subscriptions:
        if sub.status != "active":
            continue
        row = rows.setdefault(sub.category, CategoryBreakdown(sub.category))
        amounts = row.amounts.setdefault(sub.currency, {"monthly": 0, "yearly": 0})
        amounts["monthly"] += monthly_cents(sub.price_cents, sub.billing_cycle)
        amounts["yearly"] += yearly_cents(sub.price_cents, sub.billing_cycle)

    breakdown: list[CategoryBreakdown] = []
    for category in sorted(rows):
        row = rows[category]
        row.amounts = {
            currency: row.amounts.get(currency, {"monthly": 0, "yearly": 0})
            for currency in currencies
        }
        breakdown.append(row)
    return breakdown


def category_totals(rows: list[CategoryBreakdown], currencies: list[str]) -> dict[str, dict[str, int]]:
    totals = {currency: {"monthly": 0, "yearly": 0} for currency in currencies}
    for row in rows:
        for currency in currencies:
            amounts = row.amounts.get(currency, {"monthly": 0, "yearly": 0})
            totals[currency]["monthly"] += amounts["monthly"]
            totals[currency]["yearly"] += amounts["yearly"]
    return totals
