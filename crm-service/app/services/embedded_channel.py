"""
services/embedded_channel.py — Built-in delivery simulator (single-service mode).

Used when CHANNEL_SERVICE_URL is not set, e.g. on a one-service Render deploy.
It behaves like channel-service/app/simulator.py — same odds, same delays —
but runs inside the CRM process and writes receipts straight to the database
instead of POSTing them back over HTTP. So there are no URLs or shared
secrets to configure.

  - 85% delivered / 15% failed      (after 1–4 s)
  - 60% of delivered get opened     (after 3–8 s more)
  - 35% of opened get clicked       (after 2–6 s more)
"""

from __future__ import annotations
import asyncio
import logging
import random
from datetime import datetime, timezone

from app.db.database import AsyncSessionLocal
from app.services.receipt_service import apply_receipt

logger = logging.getLogger(__name__)

# Strong references so running simulations aren't garbage-collected mid-way.
_tasks: set[asyncio.Task] = set()


async def _receipt(external_id: str, status: str) -> None:
    """Record one delivery event for a message, using its own short DB session."""
    try:
        async with AsyncSessionLocal() as db:
            await apply_receipt(db, external_id, status, datetime.now(timezone.utc))
    except Exception as e:  # a failed receipt must not kill the simulation
        logger.warning(f"[EMBEDDED CHANNEL] receipt {external_id} -> {status} failed: {e}")


async def _simulate(external_id: str) -> None:
    """Play out one message's journey: delivered or failed, then maybe opened, then maybe clicked."""
    await asyncio.sleep(random.uniform(1, 4))
    if random.random() >= 0.85:
        await _receipt(external_id, "failed")
        return
    await _receipt(external_id, "delivered")

    await asyncio.sleep(random.uniform(3, 8))
    if random.random() < 0.60:
        await _receipt(external_id, "opened")
        await asyncio.sleep(random.uniform(2, 6))
        if random.random() < 0.35:
            await _receipt(external_id, "clicked")


def send_batch(items: list[dict]) -> dict[str, str]:
    """Accept a batch (same shape as the channel service's /send) and start simulating each message."""
    for item in items:
        task = asyncio.create_task(_simulate(item["external_id"]))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    return {item["external_id"]: "accepted" for item in items}
