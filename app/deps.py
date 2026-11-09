"""Request dependencies: session identity, login gate and CSRF checks."""

from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import new_csrf_token, tokens_match


class LoginRequired(Exception):
    """Raised by :func:`require_user`; the app redirects to the login page."""

    def __init__(self, next_path: str) -> None:
        super().__init__("login required")
        self.next_path = next_path


def get_current_user(request: Request, db: Session) -> User | None:
    """Resolve the signed-in user from the session cookie, or ``None``."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.get(User, int(user_id))
    if user is None:  # account deleted while the cookie was alive
        request.session.clear()
        return None
    return user


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Gate for authenticated pages: redirects to /login when signed out."""
    user = get_current_user(request, db)
    if user is None:
        raise LoginRequired(request.url.path)
    request.state.current_user = user
    return user


def ensure_csrf_token(request: Request) -> str:
    """Return the session-bound CSRF token, creating it on first use."""
    token = request.session.get("csrf_token")
    if not token:
        token = new_csrf_token()
        request.session["csrf_token"] = token
    return token


def csrf_is_valid(request: Request, submitted: str | None) -> bool:
    return tokens_match(request.session.get("csrf_token"), submitted)
