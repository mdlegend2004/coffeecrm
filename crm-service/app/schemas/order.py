"""
schemas/order.py — Pydantic v2 schemas for Order endpoints.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class OrderResponse(BaseModel):
    """A single order as returned by the API."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    amount: float
    product_name: Optional[str]
    product_category: Optional[str]
    status: str
    ordered_at: datetime
