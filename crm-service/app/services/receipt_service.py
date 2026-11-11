"""
services/receipt_service.py — Apply one delivery receipt to a Communication row.

Shared by both delivery modes:
  - the HTTP webhook POST /api/receipts/callback (separate channel service), and
  - services/embedded_channel.py (built-in simulator, single-service deploys).

Rules:
  - Unknown external_id → ignored (makes retries safe / idempotent).
  - Status only moves forward in the funnel, so a late or retried receipt can't
    downgrade e.g. "clicked" back to "delivered".
  - 15% of clicks become "converted" (simulated conversion tracking).
"""

from __future__ import annotations
import random
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.communication import Communication

# Position of each status in the funnel; higher = further along.
_RANK = {"queued": 0, "sent": 1, "failed": 1, "delivered": 2, "opened": 3,
         "read": 4, "clicked": 5, "converted": 6}


async def apply_receipt(db: AsyncSession, external_id: str, status: str, ts: datetime) -> None:
    """Update the message identified by `external_id` to `status` (at time `ts`) and commit."""
    result = await db.execute(
        select(Communication).where(Communication.external_id == external_id)
    )
    comm = result.scalar_one_or_none()
    if not comm:
        return

    status = status.lower()
    # DB columns are TIMESTAMP WITHOUT TIME ZONE
    ts = ts.replace(tzinfo=None)

    if status != "failed" and _RANK.get(status, 0) <= _RANK.get(comm.status, 0):
        return
    if status == "failed" and _RANK.get(comm.status, 0) >= _RANK["delivered"]:
        return

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
        if random.random() < 0.15:
            comm.status = "converted"
            comm.converted_at = datetime.utcnow()

    await db.commit()
