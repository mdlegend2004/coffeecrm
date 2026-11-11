"""
schemas/customer.py — Pydantic v2 schemas for Customer endpoints.

Using model_config = ConfigDict(from_attributes=True) instead of
the deprecated Pydantic v1 class Config: orm_mode = True.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, ConfigDict


class CustomerCreate(BaseModel):
    """Body for creating a customer (single or bulk). Email must be valid and unique."""
    name: str
    email: EmailStr
    phone: Optional[str] = None
    city: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    tags: Optional[List[str]] = None


class OrderSummary(BaseModel):
    """Lightweight order summary embedded in CustomerResponse."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_name: Optional[str]
    product_category: Optional[str]
    amount: float
    status: str
    ordered_at: datetime


class CustomerResponse(BaseModel):
    """A customer as returned by the API; `orders` is filled only on the detail endpoint."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    phone: Optional[str]
    city: Optional[str]
    gender: Optional[str]
    age: Optional[int]
    total_spent: float
    purchase_count: int
    last_purchase_date: Optional[datetime]
    tags: Optional[List[str]]
    created_at: datetime
    orders: Optional[List[OrderSummary]] = None

    @classmethod
    def from_customer(cls, customer, orders=None) -> "CustomerResponse":
        """Build a response from a Customer row using only its plain columns.

        Reading `customer.orders` directly would make SQLAlchemy lazy-load the
        relationship, which crashes under async (MissingGreenlet). Pass the
        orders in explicitly when you have them.
        """
        data = {col.key: getattr(customer, col.key) for col in customer.__table__.columns}
        data["orders"] = [OrderSummary.model_validate(o) for o in orders] if orders is not None else None
        return cls.model_validate(data)


class CustomerListResponse(BaseModel):
    """One page of customers plus the total match count for pagination."""
    items: List[CustomerResponse]
    total: int
    page: int
    limit: int
