"""Jinja2 environment: filters and globals shared by every template."""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR
from app.models import BILLING_CYCLES, CATEGORIES, CURRENCIES, REMINDER_DAYS
from app.services.spend import CYCLE_UNIT, format_cents

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


def _human_date(value: date | datetime | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        value = value.date()
    return f"{value.day} {value.strftime('%b %Y')}"


def _human_datetime(value: datetime | None) -> str:
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return f"{value.day} {value.strftime('%b %Y, %H:%M')} UTC"


templates.env.filters["money"] = format_cents
templates.env.filters["cycle_unit"] = lambda cycle: CYCLE_UNIT.get(cycle, cycle)
templates.env.filters["human_date"] = _human_date
templates.env.filters["human_datetime"] = _human_datetime

templates.env.globals.update(
    {
        "categories": CATEGORIES,
        "currencies": CURRENCIES,
        "billing_cycles": BILLING_CYCLES,
        "reminder_days": REMINDER_DAYS,
        "app_name": "Renewly",
    }
)
