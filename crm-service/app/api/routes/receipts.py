"""
api/routes/receipts.py — Inbound delivery receipt webhook.

Design:
  - POST /callback is called by the separate channel service (two-service mode).
    In single-service mode the built-in simulator applies receipts directly
    and this endpoint is unused.
  - Idempotent: unknown external_ids are ignored, so channel retries are safe.
  - The update rules live in services/receipt_service.py (shared by both modes).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.communication import ReceiptCallback
from app.services.receipt_service import apply_receipt

router = APIRouter()


@router.post("/callback")
async def receipt_callback(
    body: ReceiptCallback,
    db: AsyncSession = Depends(get_db),
):
    """
    Update Communication status based on delivery receipt.
    Always returns 200 — idempotent to allow safe retries from channel service.
    """
    await apply_receipt(db, body.external_id, body.status, body.timestamp)
    return {"received": True}
