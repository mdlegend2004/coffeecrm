"""
models/campaign.py — Campaign ORM model.

channel Enum is intentionally narrow (whatsapp/sms/email/rcs) — adding
new channels later requires a migration, but that's acceptable because
channel type affects business logic (message length limits, rate limits).
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Column, ForeignKey, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.database import Base


class Campaign(Base):
    """A message blast to one segment over one channel. Status: draft -> running -> completed (or failed)."""
    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(150), nullable=False)
    segment_id = Column(UUID(as_uuid=True), ForeignKey("segments.id"), nullable=True)
    channel = Column(
        Enum("whatsapp", "sms", "email", "rcs", name="campaign_channel"),
        nullable=False,
    )
    message_template = Column(Text, nullable=False)
    ai_generated_message = Column(Boolean, default=False)
    status = Column(
        Enum("draft", "running", "completed", "failed", name="campaign_status"),
        default="draft",
        nullable=False,
    )
    scheduled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    segment = relationship("Segment", back_populates="campaigns")
    communications = relationship("Communication", back_populates="campaign")
