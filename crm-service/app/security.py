"""
security.py — Optional site-wide password + service-to-service secret.

Two independent protections, each switched on only when its env var is set,
so local development (no env vars) works exactly as before:

  APP_PASSWORD     → every request needs HTTP Basic auth (the browser shows its
                     own username/password box once, then remembers it).
                     Username is APP_USERNAME (default "admin").
  CALLBACK_SECRET  → /api/receipts/callback must carry the header
                     X-Callback-Secret: <secret>. The channel service sends it.

/health is always open so Render's health checks work.
/api/receipts/callback skips the password (the channel service can't type one)
and is protected by CALLBACK_SECRET instead.
"""

from __future__ import annotations
import base64
import os
import secrets

from dotenv import load_dotenv
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

load_dotenv()

APP_USERNAME = os.getenv("APP_USERNAME", "admin")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
CALLBACK_SECRET = os.getenv("CALLBACK_SECRET", "")

OPEN_PATHS = {"/health"}
CALLBACK_PATH = "/api/receipts/callback"


def _same(a: str, b: str) -> bool:
    """Compare two strings in constant time (avoids leaking how many characters matched)."""
    return secrets.compare_digest(a.encode(), b.encode())


def _basic_auth_ok(header: str | None) -> bool:
    """Return True if an `Authorization: Basic ...` header holds the right username and password."""
    if not header or not header.startswith("Basic "):
        return False
    try:
        user, _, pwd = base64.b64decode(header[6:]).decode().partition(":")
    except Exception:
        return False
    return _same(user, APP_USERNAME) and _same(pwd, APP_PASSWORD)


async def access_guard(request: Request, call_next):
    """HTTP middleware: let the request through only if it passes the checks described above."""
    path = request.url.path

    if path in OPEN_PATHS or request.method == "OPTIONS":
        return await call_next(request)

    if path == CALLBACK_PATH:
        if CALLBACK_SECRET and not _same(request.headers.get("x-callback-secret", ""), CALLBACK_SECRET):
            return JSONResponse({"detail": "Invalid callback secret"}, status_code=403)
        return await call_next(request)

    if APP_PASSWORD and not _basic_auth_ok(request.headers.get("authorization")):
        return Response(
            "Password required",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="BrewCo CRM", charset="UTF-8"'},
        )

    return await call_next(request)
