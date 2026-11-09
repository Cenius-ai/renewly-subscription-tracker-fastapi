"""Sign-up, sign-in and sign-out."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import ratelimit
from app.db import get_db
from app.deps import csrf_is_valid, ensure_csrf_token, get_current_user
from app.models import User
from app.security import hash_password, new_csrf_token, verify_password
from app.validators import validate_signup_form
from app.web import flash, render, safe_next

router = APIRouter()

GENERIC_LOGIN_ERROR = "Email or password is incorrect."
EXPIRED_SESSION_ERROR = "Your session expired. Please try again — nothing was changed."


@router.get("/login")
def login_page(
    request: Request,
    db: Session = Depends(get_db),
    next_path: str = Query(default="", alias="next"),
):
    if get_current_user(request, db) is not None:
        return RedirectResponse("/dashboard", status_code=302)
    return render(
        request,
        "login.html",
        db=db,
        email="",
        error=None,
        next_url=safe_next(next_path),
    )


@router.post("/login")
def login_submit(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(default=""),
    password: str = Form(default=""),
    csrf_token: str = Form(default=""),
    next_path: str = Form(default="", alias="next"),
):
    destination = safe_next(next_path)
    if not csrf_is_valid(request, csrf_token):
        ensure_csrf_token(request)
        return render(
            request,
            "login.html",
            db=db,
            status_code=400,
            email=email.strip(),
            error=EXPIRED_SESSION_ERROR,
            next_url=destination,
        )

    client_key = request.client.host if request.client else "unknown"
    if ratelimit.is_locked(client_key):
        return render(
            request,
            "login.html",
            db=db,
            status_code=429,
            email=email.strip(),
            error="Too many failed attempts. Wait a few minutes and try again.",
            next_url=destination,
        )

    account = db.scalar(select(User).where(User.email == email.strip().lower()))
    if account is None or not verify_password(password, account.password_hash):
        ratelimit.record_failure(client_key)
        return render(
            request,
            "login.html",
            db=db,
            status_code=400,
            email=email.strip(),
            error=GENERIC_LOGIN_ERROR,
            next_url=destination,
        )

    ratelimit.clear_failures(client_key)
    # Rotate the session on login (defends against session fixation) and keep
    # a fresh CSRF token bound to the new session.
    request.session.clear()
    request.session["user_id"] = account.id
    request.session["csrf_token"] = new_csrf_token()
    return RedirectResponse(destination or "/dashboard", status_code=302)


@router.get("/signup")
def signup_page(request: Request, db: Session = Depends(get_db)):
    if get_current_user(request, db) is not None:
        return RedirectResponse("/dashboard", status_code=302)
    return render(request, "signup.html", db=db, email="", values={}, errors={})


@router.post("/signup")
def signup_submit(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(default=""),
    password: str = Form(default=""),
    confirm_password: str = Form(default=""),
    csrf_token: str = Form(default=""),
):
    form = {
        "email": email,
        "password": password,
        "confirm_password": confirm_password,
    }
    if not csrf_is_valid(request, csrf_token):
        return render(
            request,
            "signup.html",
            db=db,
            status_code=400,
            email=email.strip(),
            values={"email": email.strip()},
            errors={"form": EXPIRED_SESSION_ERROR},
        )

    result = validate_signup_form(form)
    errors = dict(result.errors)
    if not errors and db.scalar(select(User).where(User.email == result.email)):
        errors["email"] = "An account with this email already exists."
    if errors:
        return render(
            request,
            "signup.html",
            db=db,
            status_code=400,
            email=email.strip(),
            values={"email": email.strip()},
            errors=errors,
        )

    account = User(email=result.email, password_hash=hash_password(result.password))
    db.add(account)
    try:
        db.commit()
    except IntegrityError:
        # Two requests raced for the same address; the unique index won.
        db.rollback()
        return render(
            request,
            "signup.html",
            db=db,
            status_code=400,
            email=email.strip(),
            values={"email": email.strip()},
            errors={"email": "An account with this email already exists."},
        )

    request.session.clear()
    request.session["user_id"] = account.id
    request.session["csrf_token"] = new_csrf_token()
    flash(request, f"Welcome to Renewly, {account.email}.")
    return RedirectResponse("/dashboard", status_code=302)


@router.post("/logout")
def logout(
    request: Request,
    csrf_token: str = Form(default=""),
):
    if not csrf_is_valid(request, csrf_token):
        return render(
            request,
            "error.html",
            status_code=400,
            error_title="That sign-out link expired",
            error_body=EXPIRED_SESSION_ERROR,
        )
    request.session.clear()
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("renewly_session")
    return response
