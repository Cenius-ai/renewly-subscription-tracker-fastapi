"""Server-side validation for every form post.

The browser's HTML attributes are a convenience only: all rules below run on
the server, independent of what the client sends.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from app.models import BILLING_CYCLES, CATEGORIES, CURRENCIES, REMINDER_DAYS
from app.services.spend import MAX_PRICE_CENTS, format_cents

_PRICE_RE = re.compile(r"^\d{1,9}(?:[.,]\d{1,3})?$")
MIN_DATE = date(1970, 1, 1)
MAX_DATE = date(2100, 12, 31)


@dataclass
class SubscriptionInput:
    name: str
    category: str
    price_cents: int
    currency: str
    billing_cycle: str
    next_renewal_date: date
    reminder_days: int


@dataclass
class SubscriptionFormResult:
    data: SubscriptionInput | None
    errors: dict[str, str]
    #: Raw submitted strings, so a failed submit keeps every typed value.
    values: dict[str, str]

    @property
    def ok(self) -> bool:
        return self.data is not None


def blank_values(today: date | None = None) -> dict[str, str]:
    """Defaults for the create form.

    Cycle, currency, lead time and a renewal date 30 days out are pre-filled so
    the form can be submitted (and adjusted) in one pass.
    """
    start = today or date.today()
    return {
        "name": "",
        "category": CATEGORIES[0],
        "price": "",
        "currency": "USD",
        "billing_cycle": "monthly",
        "next_renewal_date": (start + timedelta(days=30)).isoformat(),
        "reminder_days": "7",
    }


def parse_price_cents(raw: str) -> tuple[int | None, str | None]:
    """Parse a human price into cents; returns ``(cents, error)``."""
    value = (raw or "").strip().replace(",", ".")
    if not value:
        return None, "Enter a price."
    if not _PRICE_RE.match(value):
        return None, "Enter a price with digits and at most two decimals."
    whole, _, fraction = value.partition(".")
    if len(fraction) > 2:
        return None, "Enter a price with at most two decimals."
    cents = int(whole) * 100 + int(fraction.ljust(2, "0") or "0")
    if cents <= 0:
        return None, "Price must be greater than 0."
    if cents > MAX_PRICE_CENTS:
        return None, f"Price must be at most {format_cents(MAX_PRICE_CENTS)}."
    return cents, None


def validate_subscription_form(form: dict[str, str]) -> SubscriptionFormResult:
    values = {
        "name": (form.get("name") or "").strip(),
        "category": (form.get("category") or "").strip(),
        "price": (form.get("price") or "").strip(),
        "currency": (form.get("currency") or "").strip(),
        "billing_cycle": (form.get("billing_cycle") or "").strip(),
        "next_renewal_date": (form.get("next_renewal_date") or "").strip(),
        "reminder_days": (form.get("reminder_days") or "").strip(),
    }
    errors: dict[str, str] = {}

    name = values["name"]
    if not name:
        errors["name"] = "Enter a name for this subscription."
    elif len(name) > 120:
        errors["name"] = "Keep the name to 120 characters or fewer."

    category = values["category"]
    if category not in CATEGORIES:
        errors["category"] = "Choose a category from the list."

    price_cents, price_error = parse_price_cents(values["price"])
    if price_error:
        errors["price"] = price_error

    currency = values["currency"]
    if currency not in CURRENCIES:
        errors["currency"] = "Choose a supported currency."

    billing_cycle = values["billing_cycle"]
    if billing_cycle not in BILLING_CYCLES:
        errors["billing_cycle"] = "Choose weekly, monthly or yearly."

    next_renewal: date | None = None
    raw_date = values["next_renewal_date"]
    if not raw_date:
        errors["next_renewal_date"] = "Enter the next renewal date."
    else:
        try:
            next_renewal = date.fromisoformat(raw_date)
        except ValueError:
            errors["next_renewal_date"] = "Enter a real date (YYYY-MM-DD)."
        else:
            if not (MIN_DATE <= next_renewal <= MAX_DATE):
                errors["next_renewal_date"] = "Enter a date between 1970 and 2100."
                next_renewal = None

    reminder_days = 0
    try:
        reminder_days = int(values["reminder_days"])
    except (TypeError, ValueError):
        errors["reminder_days"] = "Choose a reminder lead time."
    else:
        if reminder_days not in REMINDER_DAYS:
            errors["reminder_days"] = "Choose 1, 3, 7, 14 or 30 days."

    if errors:
        return SubscriptionFormResult(data=None, errors=errors, values=values)

    assert price_cents is not None and next_renewal is not None
    return SubscriptionFormResult(
        data=SubscriptionInput(
            name=name,
            category=category,
            price_cents=price_cents,
            currency=currency,
            billing_cycle=billing_cycle,
            next_renewal_date=next_renewal,
            reminder_days=reminder_days,
        ),
        errors={},
        values=values,
    )


@dataclass
class SignupFormResult:
    email: str
    password: str
    errors: dict[str, str]

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_signup_form(form: dict[str, str]) -> SignupFormResult:
    from app.security import is_valid_email

    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""
    confirm = form.get("confirm_password") or ""
    errors: dict[str, str] = {}

    if not email:
        errors["email"] = "Enter your email address."
    elif not is_valid_email(email):
        errors["email"] = "Enter a valid email address."

    if not password:
        errors["password"] = "Choose a password."
    elif len(password) < 8:
        errors["password"] = "Use at least 8 characters."
    elif len(password) > 200:
        errors["password"] = "Keep the password to 200 characters or fewer."

    if not confirm:
        errors["confirm_password"] = "Repeat your password."
    elif password and confirm != password:
        errors["confirm_password"] = "Passwords do not match."

    return SignupFormResult(email=email, password=password, errors=errors)
