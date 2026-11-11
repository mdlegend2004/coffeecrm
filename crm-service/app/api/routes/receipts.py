"""
api/routes/receipts.py — Inbound delivery receipt webhook.

Design:
  - POST /callback is called by the channel service simulator.
  - Idempotent: if external_id not found, return 200 immediately.
    This handles retries from the channel service safely.
  - Conversion is probabilistic (15% chance on click) — simulates
    real-world CRM conversion tracking without a separate event system.
"""

from __future__ import annotations
import random
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.communication import Communication
from app.schemas.communication import ReceiptCallback

router = APIRouter()

_RANK = {"queued": 0, "sent": 1, "failed": 1, "delivered": 2, "opened": 3,
         "read": 4, "clicked": 5, "converted": 6}


@router.post("/callback")
async def receipt_callback(
    body: ReceiptCallback,
    db: AsyncSession = Depends(get_db),
):
    """
    Update Communication status based on delivery receipt.
    Always returns 200 — idempotent to allow safe retries from channel service.
    """
    result = await db.execute(
        select(Communication).where(Communication.external_id == body.external_id)
    )
    comm = result.scalar_one_or_none()

    # Idempotent — unknown external_id means it was already cleaned up or never existed
    if not comm:
        return {"received": True}

    now = datetime.utcnow()
    status = body.status.lower()
    # Strip timezone info — DB columns are TIMESTAMP WITHOUT TIME ZONE
    ts = body.timestamp.replace(tzinfo=None)

    # Never move a message backwards in the funnel (retried / out-of-order
    # callbacks would otherwise downgrade e.g. "clicked" back to "delivered").
    if _RANK.get(status, 0) <= _RANK.get(comm.status, 0) and status != "failed":
        return {"received": True}
    if status == "failed" and _RANK.get(comm.status, 0) >= _RANK["delivered"]:
        return {"received": True}

    if status == "delivered":
        comm.status = "delivered"
        comm.delivered_at = ts
    elif status == "failed":
        comm.status = "failed"
    elif status == "opened":
        comm.status = "opened"
        comm.opened_at = ts
    elif status == "read":
        comm.status = "read"
    elif status == "clicked":
        comm.status = "clicked"
        comm.clicked_at = ts
        # 15% probabilistic conversion on click
        if random.random() < 0.15:
            comm.status = "converted"
            comm.converted_at = now

    await db.commit()
    return {"received": True}
