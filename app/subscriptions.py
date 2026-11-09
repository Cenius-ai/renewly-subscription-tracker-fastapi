"""Subscription create, list, edit, cancel/resume and delete.

Every query below is scoped by the signed-in user id: another account's
subscription id resolves to the friendly 404 page, never to their data.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import csrf_is_valid, require_user
from app.models import Subscription, User, utcnow
from app.services.renewals import roll_forward
from app.validators import (
    SubscriptionInput,
    blank_values,
    validate_subscription_form,
)
from app.web import flash, render

router = APIRouter()

EXPIRED_SESSION_ERROR = "Your session expired. Please try again — nothing was saved."

STATUS_FILTERS: tuple[str, ...] = ("all", "active", "cancelled")


def _list_view(
    request: Request,
    db: Session,
    user: User,
    *,
    status_filter: str = "all",
    status_code: int = 200,
):
    all_subscriptions = list(
        db.scalars(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.status, Subscription.name)
        )
    )
    today = date.today()
    rows = []
    for subscription in all_subscriptions:
        if status_filter != "all" and subscription.status != status_filter:
            continue
        effective = roll_forward(subscription.next_renewal_date, subscription.billing_cycle, today)
        rows.append(
            {
                "subscription": subscription,
                "effective_date": effective,
                "rolled": effective != subscription.next_renewal_date,
            }
        )

    filter_options = [
        {
            "label": f"All ({len(all_subscriptions)})",
            "href": "/subscriptions",
            "active": status_filter == "all",
        },
        {
            "label": "Active ("
            + str(sum(1 for sub in all_subscriptions if sub.status == "active"))
            + ")",
            "href": "/subscriptions?status=active",
            "active": status_filter == "active",
        },
        {
            "label": "Cancelled ("
            + str(sum(1 for sub in all_subscriptions if sub.status == "cancelled"))
            + ")",
            "href": "/subscriptions?status=cancelled",
            "active": status_filter == "cancelled",
        },
    ]

    return render(
        request,
        "subscriptions.html",
        db=db,
        user=user,
        status_code=status_code,
        subscriptions=rows,
        rows=rows,
        total_count=len(all_subscriptions),
        active_count=sum(1 for sub in all_subscriptions if sub.status == "active"),
        cancelled_count=sum(1 for sub in all_subscriptions if sub.status == "cancelled"),
        filter_options=filter_options,
        status_filter=status_filter,
        today=today,
    )


def _parse_id(raw: str) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=404, detail="Subscription not found")
    if value <= 0:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return value


def _owned_subscription(db: Session, user: User, raw_id: str) -> Subscription:
    subscription = db.scalar(
        select(Subscription).where(
            Subscription.id == _parse_id(raw_id),
            Subscription.user_id == user.id,
        )
    )
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription


def _apply(subscription: Subscription, data: SubscriptionInput) -> None:
    subscription.name = data.name
    subscription.category = data.category
    subscription.price_cents = data.price_cents
    subscription.currency = data.currency
    subscription.billing_cycle = data.billing_cycle
    subscription.next_renewal_date = data.next_renewal_date
    subscription.reminder_days = data.reminder_days
    subscription.updated_at = utcnow()


def _csrf_failure(request: Request, db: Session, user: User):
    """A state-changing post without the session token is rejected with 400."""
    return render(
        request,
        "error.html",
        db=db,
        user=user,
        status_code=400,
        error_title="That form expired",
        error_body=EXPIRED_SESSION_ERROR,
    )


@router.get("/subscriptions")
def list_subscriptions(
    request: Request,
    status: str = Query(default="all"),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    status_filter = status if status in STATUS_FILTERS else "all"
    return _list_view(request, db, user, status_filter=status_filter)


@router.get("/subscriptions/new")
def new_subscription_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    return render(
        request,
        "subscription_form.html",
        db=db,
        user=user,
        mode="new",
        subscription=None,
        values=blank_values(),
        errors={},
        form_title="Add a subscription",
    )


@router.post("/subscriptions")
def create_subscription(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    name: str = Form(default=""),
    category: str = Form(default=""),
    price: str = Form(default=""),
    currency: str = Form(default=""),
    billing_cycle: str = Form(default=""),
    next_renewal_date: str = Form(default=""),
    reminder_days: str = Form(default=""),
    csrf_token: str = Form(default=""),
):
    form = {
        "name": name,
        "category": category,
        "price": price,
        "currency": currency,
        "billing_cycle": billing_cycle,
        "next_renewal_date": next_renewal_date,
        "reminder_days": reminder_days,
    }

    def rerender(errors: dict[str, str], status_code: int = 400):
        return render(
            request,
            "subscription_form.html",
            db=db,
            user=user,
            status_code=status_code,
            mode="new",
            subscription=None,
            values=form,
            errors=errors,
            form_title="Add a subscription",
        )

    if not csrf_is_valid(request, csrf_token):
        return rerender({"form": EXPIRED_SESSION_ERROR})

    result = validate_subscription_form(form)
    errors = dict(result.errors)
    if result.ok and result.data is not None:
        if db.scalar(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.name == result.data.name,
            )
        ):
            errors["name"] = "You already track a subscription with this name."
    if errors or result.data is None:
        return rerender(errors)

    subscription = Subscription(user_id=user.id, status="active")
    _apply(subscription, result.data)
    db.add(subscription)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return rerender({"name": "You already track a subscription with this name."})

    flash(request, f"Added {subscription.name}.")
    return RedirectResponse("/subscriptions", status_code=302)


@router.get("/subscriptions/{subscription_id}/edit")
def edit_subscription_form(
    request: Request,
    subscription_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    subscription = _owned_subscription(db, user, subscription_id)
    values = {
        "name": subscription.name,
        "category": subscription.category,
        "price": f"{subscription.price_cents // 100}.{subscription.price_cents % 100:02d}",
        "currency": subscription.currency,
        "billing_cycle": subscription.billing_cycle,
        "next_renewal_date": subscription.next_renewal_date.isoformat(),
        "reminder_days": str(subscription.reminder_days),
    }
    return render(
        request,
        "subscription_form.html",
        db=db,
        user=user,
        mode="edit",
        subscription=subscription,
        values=values,
        errors={},
        form_title=f"Edit {subscription.name}",
    )


@router.post("/subscriptions/{subscription_id}")
def update_subscription(
    request: Request,
    subscription_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    name: str = Form(default=""),
    category: str = Form(default=""),
    price: str = Form(default=""),
    currency: str = Form(default=""),
    billing_cycle: str = Form(default=""),
    next_renewal_date: str = Form(default=""),
    reminder_days: str = Form(default=""),
    csrf_token: str = Form(default=""),
):
    subscription = _owned_subscription(db, user, subscription_id)
    form = {
        "name": name,
        "category": category,
        "price": price,
        "currency": currency,
        "billing_cycle": billing_cycle,
        "next_renewal_date": next_renewal_date,
        "reminder_days": reminder_days,
    }

    def rerender(errors: dict[str, str], status_code: int = 400):
        return render(
            request,
            "subscription_form.html",
            db=db,
            user=user,
            status_code=status_code,
            mode="edit",
            subscription=subscription,
            values=form,
            errors=errors,
            form_title=f"Edit {subscription.name}",
        )

    if not csrf_is_valid(request, csrf_token):
        return rerender({"form": EXPIRED_SESSION_ERROR})

    result = validate_subscription_form(form)
    errors = dict(result.errors)
    if result.ok and result.data is not None:
        clash = db.scalar(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.name == result.data.name,
                Subscription.id != subscription.id,
            )
        )
        if clash is not None:
            errors["name"] = "You already track a subscription with this name."
    if errors or result.data is None:
        return rerender(errors)

    _apply(subscription, result.data)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return rerender({"name": "You already track a subscription with this name."})

    flash(request, f"Saved changes to {subscription.name}.")
    return RedirectResponse("/subscriptions", status_code=302)


@router.post("/subscriptions/{subscription_id}/cancel")
def cancel_subscription(
    request: Request,
    subscription_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    csrf_token: str = Form(default=""),
):
    subscription = _owned_subscription(db, user, subscription_id)
    if not csrf_is_valid(request, csrf_token):
        return _csrf_failure(request, db, user)
    if subscription.status != "cancelled":
        subscription.status = "cancelled"
        subscription.cancelled_at = utcnow()
        subscription.updated_at = utcnow()
        db.commit()
        flash(request, f"Cancelled {subscription.name}. Its cost is out of your totals.")
    return RedirectResponse("/subscriptions", status_code=302)


@router.post("/subscriptions/{subscription_id}/resume")
def resume_subscription(
    request: Request,
    subscription_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    csrf_token: str = Form(default=""),
):
    subscription = _owned_subscription(db, user, subscription_id)
    if not csrf_is_valid(request, csrf_token):
        return _csrf_failure(request, db, user)
    if subscription.status != "active":
        subscription.status = "active"
        subscription.cancelled_at = None
        subscription.updated_at = utcnow()
        db.commit()
        flash(request, f"Resumed {subscription.name}. It counts toward spend again.")
    return RedirectResponse("/subscriptions", status_code=302)


@router.post("/subscriptions/{subscription_id}/delete")
def delete_subscription(
    request: Request,
    subscription_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    csrf_token: str = Form(default=""),
):
    subscription = _owned_subscription(db, user, subscription_id)
    if not csrf_is_valid(request, csrf_token):
        return _csrf_failure(request, db, user)
    name = subscription.name
    db.delete(subscription)
    db.commit()
    flash(request, f"Deleted {name}.")
    return RedirectResponse("/subscriptions", status_code=302)
