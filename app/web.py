"""Shared view helpers: page rendering, flash messages and the command palette."""

from __future__ import annotations

from datetime import date
from urllib.parse import urlsplit

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import ensure_csrf_token
from app.models import Subscription, User
from app.templating import templates

_MAX_FLASHES = 4


def flash(request: Request, message: str) -> None:
    """Queue a one-shot status message shown on the next rendered page."""
    queue = list(request.session.get("flash") or [])
    queue.append(message)
    request.session["flash"] = queue[-_MAX_FLASHES:]


def _pop_flashes(request: Request) -> list[str]:
    return list(request.session.pop("flash", []) or [])


def safe_next(next_path: str | None) -> str:
    """Only allow same-site relative paths as a post-login destination."""
    candidate = (next_path or "").strip()
    if not candidate or not candidate.startswith("/") or candidate.startswith("//"):
        return ""
    parts = urlsplit(candidate)
    if parts.scheme or parts.netloc:
        return ""
    return parts.path + (f"?{parts.query}" if parts.query else "")


def palette_items(db: Session | None, user: User | None) -> list[dict[str, str]]:
    """Everything the command palette can jump to for this user."""
    if user is None:
        return [
            {"label": "Sign in", "hint": "Account", "href": "/login"},
            {"label": "Create account", "hint": "Account", "href": "/signup"},
        ]
    items = [
        {"label": "Dashboard", "hint": "Spend and renewals", "href": "/dashboard"},
        {"label": "Subscriptions", "hint": "Everything you track", "href": "/subscriptions"},
        {"label": "New subscription", "hint": "Add a charge", "href": "/subscriptions/new"},
    ]
    if db is not None:
        rows = db.scalars(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.status, Subscription.name)
        )
        for sub in rows:
            items.append(
                {
                    "label": sub.name,
                    "hint": f"{sub.category} · {sub.currency} · {sub.status}",
                    "href": f"/subscriptions/{sub.id}/edit",
                }
            )
    return items


def render(
    request: Request,
    template_name: str,
    *,
    db: Session | None = None,
    user: User | None = None,
    status_code: int = 200,
    **context: object,
):
    """Render a template with the shared shell context filled in."""
    if user is None:
        user = getattr(request.state, "current_user", None)
    context.setdefault("current_user", user)
    context["csrf_token"] = ensure_csrf_token(request)
    context["flashes"] = _pop_flashes(request)
    context["today"] = date.today()
    context.setdefault("palette_items", palette_items(db, user))
    return templates.TemplateResponse(request, template_name, context, status_code=status_code)
