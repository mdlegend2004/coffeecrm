"""
models/customer.py — Customer ORM model.

tags is stored as a native Postgres ARRAY(String) which lets the
RulesEngine use PostgreSQL's @> (contains) operator efficiently.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Column
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from app.db.database import Base


class Customer(Base):
    """A shopper. total_spent / purchase_count are derived from their completed orders."""
    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    phone = Column(String(20))
    city = Column(String(50))
    gender = Column(String(10))
    age = Column(Integer)
    total_spent = Column(Float, default=0.0)
    last_purchase_date = Column(DateTime, nullable=True)
    purchase_count = Column(Integer, default=0)
    # ARRAY(String) — native Postgres array; supports 'contains' rule op
    tags = Column(ARRAY(String), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    orders = relationship("Order", back_populates="customer", lazy="select")
    communications = relationship("Communication", back_populates="customer", lazy="select")
