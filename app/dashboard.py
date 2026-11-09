"""The dashboard: spend totals, category breakdown, renewals and savings."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_user
from app.models import Subscription, User
from app.services.renewals import upcoming_renewals
from app.services.spend import (
    active_totals,
    category_breakdown,
    category_totals,
    currencies_in_use,
    savings_totals,
)
from app.web import render

router = APIRouter()


@router.get("/dashboard")
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    subscriptions = list(
        db.scalars(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.status, Subscription.name)
        )
    )
    today = date.today()

    totals = active_totals(subscriptions)
    savings = savings_totals(subscriptions)
    currencies = currencies_in_use(subscriptions)
    breakdown = category_breakdown(subscriptions, currencies)
    breakdown_totals = category_totals(breakdown, currencies)
    upcoming = upcoming_renewals(subscriptions, today)

    active_count = sum(1 for sub in subscriptions if sub.status == "active")
    cancelled_count = sum(1 for sub in subscriptions if sub.status == "cancelled")

    return render(
        request,
        "dashboard.html",
        db=db,
        user=user,
        subscriptions=subscriptions,
        totals=totals,
        savings=savings,
        currencies=currencies,
        breakdown=breakdown,
        breakdown_totals=breakdown_totals,
        upcoming=upcoming,
        active_count=active_count,
        cancelled_count=cancelled_count,
        total_count=len(subscriptions),
        has_active=active_count > 0,
    )
