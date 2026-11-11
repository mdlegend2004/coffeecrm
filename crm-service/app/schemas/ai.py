"""
schemas/ai.py — Pydantic v2 schemas for AI endpoints.

These schemas validate the structured JSON returned by gpt-4o-mini
before it's used to create DB records or returned to the client.
"""

from __future__ import annotations
from typing import List, Literal
from pydantic import BaseModel

from app.schemas.segment import SegmentRules
from app.schemas.customer import CustomerResponse
from app.schemas.campaign import CampaignResponse
from app.schemas.segment import SegmentResponse


# ── /api/ai/build-segment ────────────────────────────────────────────────────

class BuildSegmentRequest(BaseModel):
    """Body for POST /api/ai/build-segment: a plain-English audience description."""
    prompt: str


class BuildSegmentResponse(BaseModel):
    """AI-generated rules plus a live match count and up to 5 sample customers."""
    rules: SegmentRules
    preview_count: int
    sample_customers: List[CustomerResponse]


# ── /api/ai/write-message ────────────────────────────────────────────────────

class WriteMessageRequest(BaseModel):
    """Body for POST /api/ai/write-message: who it's for, which channel, and the goal."""
    brand_name: str
    segment_description: str
    channel: str
    goal: str


class MessageVariant(BaseModel):
    """One AI-written message and its tone (friendly / urgent / value-focused)."""
    tone: str
    message: str


class WriteMessageResponse(BaseModel):
    """The list of message variants returned by the AI copywriter."""
    variants: List[MessageVariant]


# ── /api/ai/insights/{campaign_id} ──────────────────────────────────────────

class InsightItem(BaseModel):
    """One AI observation about a campaign: an 'insight' or a 'recommendation'."""
    type: Literal["insight", "recommendation"]
    text: str


class CampaignInsightsResponse(BaseModel):
    """Response for GET /api/ai/insights/{id}: 3 insights + 2 recommendations."""
    insights: List[InsightItem]


# ── /api/ai/create-campaign ──────────────────────────────────────────────────

class CreateCampaignRequest(BaseModel):
    """Body for POST /api/ai/create-campaign: a one-line campaign intent."""
    intent: str


class CreateCampaignResponse(BaseModel):
    """The saved draft campaign, its new segment, all message variants, and a ready flag."""
    campaign: CampaignResponse
    segment: SegmentResponse
    message_variants: List[MessageVariant]
    ready_to_launch: bool
