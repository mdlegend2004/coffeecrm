"""
schemas/communication.py — Pydantic v2 schemas for Communication endpoints.

ReceiptCallback is the inbound webhook body from the channel service.
The timestamp field accepts ISO 8601 strings (datetime auto-parses them).
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class CommunicationResponse(BaseModel):
    """A single message row as returned by the API."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    customer_id: UUID
    channel: str
    message: str
    status: str
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    opened_at: Optional[datetime]
    clicked_at: Optional[datetime]
    converted_at: Optional[datetime]
    external_id: str


class ReceiptCallback(BaseModel):
    """Inbound delivery receipt from the channel service."""
    external_id: str
    status: str
    timestamp: datetime
