"""
models/segment.py — Segment ORM model.

rules is stored as JSON (PostgreSQL JSONB under the hood) rather than
normalised tables.  Rationale: segment rule schemas evolve frequently
in CRM products; JSON avoids constant migrations and lets the rules
engine interpret any shape of filter conditions.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, DateTime, Column, Text
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
from app.db.database import Base


class Segment(Base):
    """A saved audience: JSON `rules` evaluated by RulesEngine, plus a cached customer_count."""
    __tablename__ = "segments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(String(300), nullable=True)
    # JSON stores: { "operator": "AND", "conditions": [...] }
    rules = Column(JSON, nullable=False)
    ai_generated = Column(Boolean, default=False)
    # Cached count — recomputed on segment save; avoids full table scan on list
    customer_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    campaigns = relationship("Campaign", back_populates="segment")
