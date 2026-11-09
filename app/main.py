"""Renewly — FastAPI application (server-rendered Jinja2 pages)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app import auth, dashboard, subscriptions
from app.config import BASE_DIR, settings
from app.db import SessionLocal, init_db
from app.deps import LoginRequired, get_current_user
from app.seed import seed_demo_data
from app.web import render

logger = logging.getLogger("renewly")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Create the schema and seed demo data on every launch path."""
    init_db()
    with SessionLocal() as session:
        summary = seed_demo_data(session)
    logger.info("renewly ready; seed summary: %s", summary)
    yield


app = FastAPI(
    title="Renewly Subscription Tracker",
    description="Self-hosted subscription spend tracker.",
    version="1.0.0",
    lifespan=lifespan,
    # Every screen is HTML. There is no public JSON API to document, and the
    # bundled Swagger UI would need assets from a CDN this app never fetches.
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie=settings.session_cookie,
    max_age=settings.session_max_age,
    same_site="lax",
    https_only=False,  # previews and self-hosting run over plain HTTP
)

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "app" / "static")),
    name="static",
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(subscriptions.router)


@app.middleware("http")
async def treat_head_as_get(request: Request, call_next):
    """Answer HEAD the way a browser/probe expects from a GET page."""
    if request.method == "HEAD":
        request.scope["method"] = "GET"
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    # Everything this app loads is same-origin: no inline scripts or styles,
    # no CDN, no remote fonts.
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "font-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
    )
    return response


@app.get("/", include_in_schema=False)
def index(request: Request):
    with SessionLocal() as db:
        user = get_current_user(request, db)
    return RedirectResponse("/dashboard" if user else "/login", status_code=302)


@app.get("/health", include_in_schema=False)
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.exception_handler(LoginRequired)
def handle_login_required(request: Request, exc: LoginRequired):
    target = "/dashboard"
    if exc.next_path and not exc.next_path.startswith("/login"):
        target = exc.next_path
    return RedirectResponse(f"/login?next={target}", status_code=302)


@app.exception_handler(StarletteHTTPException)
def handle_http_exception(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return render(
            request,
            "404.html",
            status_code=404,
            page_title="Page not found",
            message="That subscription or page does not exist, or it belongs to another account.",
        )
    if exc.status_code == 405:
        return render(
            request,
            "404.html",
            status_code=405,
            page_title="Not allowed",
            message="That action is not available on this page.",
        )
    return render(
        request,
        "error.html",
        status_code=exc.status_code,
        error_title="That request did not work",
        error_body=str(exc.detail) if isinstance(exc.detail, str) else "Please try again.",
    )


@app.exception_handler(RequestValidationError)
def handle_validation_error(request: Request, exc: RequestValidationError):
    logger.info("request validation failed on %s: %s", request.url.path, exc.errors())
    return render(
        request,
        "error.html",
        status_code=400,
        error_title="That request could not be read",
        error_body="Check the values you submitted and try again.",
    )


@app.exception_handler(Exception)
def handle_unexpected_error(request: Request, exc: Exception):
    logger.exception("unhandled error on %s", request.url.path, exc_info=exc)
    return render(
        request,
        "error.html",
        status_code=500,
        error_title="Something went wrong",
        error_body="Renewly hit an unexpected problem. Your data was not changed.",
    )
