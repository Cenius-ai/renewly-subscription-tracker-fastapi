"""Root ASGI entrypoint: ``uvicorn main:app`` from the project root."""

from app.main import app

__all__ = ["app"]
