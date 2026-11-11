"""
models/order.py — Order ORM model.

product_category uses a plain string rather than Enum so we can extend
categories without a DB migration (e.g., "merchandise" later).
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Float, DateTime, Column, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.database import Base


class Order(Base):
    """One purchase by a customer (status: completed, pending or returned)."""
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    amount = Column(Float, nullable=False)
    product_name = Column(String(100))
    product_category = Column(String(50))  # "beverage" | "food"
    status = Column(
        Enum("completed", "returned", "pending", name="order_status"),
        default="completed",
        nullable=False,
    )
    ordered_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    customer = relationship("Customer", back_populates="orders")
