"""
channel-service/app/main.py — Channel simulation service.

Accepts batch message sends, simulates async delivery, and fires
receipt callbacks back to the CRM service.

Design:
  - pending_callbacks is a module-level list (in-memory store).
    At demo scale this is fine; at production scale use Redis/SQS.
  - simulate_delivery() runs as a BackgroundTask so /send returns
    instantly (matching real channel provider behaviour like Twilio).
  - retry_pending_callbacks() starts on app startup as an asyncio
    task, retrying any failed callbacks every 30 seconds.
"""

import asyncio
import os
import secrets

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException

from app.simulator import simulate_delivery, CALLBACK_SECRET
from app.callback_worker import retry_pending_callbacks

load_dotenv()

CRM_CALLBACK_URL = os.getenv("CRM_CALLBACK_URL", "http://localhost:8000")

app = FastAPI(title="BrewCo Channel Service", version="1.0.0")

# In-memory pending callback queue — populated by simulator on callback failure
pending_callbacks: list = []


@app.on_event("startup")
async def startup_event():
    """Start the background retry worker when the service boots."""
    asyncio.create_task(
        retry_pending_callbacks(pending_callbacks, CRM_CALLBACK_URL)
    )
    print(f"[CHANNEL SERVICE] Started. CRM callback URL: {CRM_CALLBACK_URL}")


@app.post("/send")
async def send_messages(payload: list[dict], x_callback_secret: str = Header(default="")):
    """
    Accept a batch of messages and simulate delivery asynchronously.
    Returns immediately with accepted count.
    When CALLBACK_SECRET is set, only callers presenting it (the CRM) are accepted.
    """
    if CALLBACK_SECRET and not secrets.compare_digest(x_callback_secret.encode(), CALLBACK_SECRET.encode()):
        raise HTTPException(status_code=403, detail="Invalid secret")
    for item in payload:
        asyncio.create_task(
            simulate_delivery(item, CRM_CALLBACK_URL, pending_callbacks)
        )
    return {"accepted": len(payload)}


@app.get("/health", tags=["system"])
async def health():
    """Liveness check: returns 200 so you (or Render) can tell the channel service is up."""
    return {"status": "ok", "service": "channel"}


@app.get("/pending-callbacks")
async def get_pending():
    """Debug endpoint: inspect pending retry queue."""
    return {
        "pending": len(pending_callbacks),
        "items": pending_callbacks[-20:],  # last 20 only
    }
