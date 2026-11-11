"""
models/communication.py — Communication ORM model.

Tracks the full delivery funnel per message:
  queued → sent → delivered → opened → read → clicked → converted

external_id is the unique ID shared with the channel service;
it's used as the key in receipt callbacks (idempotent lookups).
"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Column, ForeignKey, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.database import Base


class Communication(Base):
    """One message to one customer within a campaign.

    `external_id` is shared with the channel service so delivery callbacks can find
    this row. Status moves forward only: queued -> sent -> delivered -> opened -> clicked -> converted
    (or failed)."""
    __tablename__ = "communications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    channel = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(
        Enum(
            "queued", "sent", "delivered", "failed",
            "opened", "read", "clicked", "converted",
            name="comm_status",
        ),
        default="queued",
        nullable=False,
    )
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    converted_at = Column(DateTime, nullable=True)
    # Shared with channel service; used for callback lookup — must be unique
    external_id = Column(String(100), unique=True, nullable=False)

    # Relationships
    campaign = relationship("Campaign", back_populates="communications")
    customer = relationship("Customer", back_populates="communications")
