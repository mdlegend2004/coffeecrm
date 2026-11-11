"""
api/routes/ai.py — AI-powered CRM endpoints.

POST /build-segment     — NL → segment rules
POST /write-message     — generate 3 message variants
GET  /insights/{id}     — campaign performance insights
POST /create-campaign   — one-shot intent → campaign + segment
"""

from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.campaign import Campaign
from app.models.communication import Communication
from app.models.segment import Segment
from app.schemas.ai import (
    BuildSegmentRequest,
    BuildSegmentResponse,
    CampaignInsightsResponse,
    CreateCampaignRequest,
    CreateCampaignResponse,
    InsightItem,
    MessageVariant,
    WriteMessageRequest,
    WriteMessageResponse,
)
from app.schemas.campaign import CampaignResponse
from app.schemas.customer import CustomerResponse
from app.schemas.segment import SegmentResponse, SegmentRules
from app.services import ai_service
from app.services.segmentation import RulesEngine

def require_openai_key() -> None:
    """Dependency: answer 503 with a clear message when OPENAI_API_KEY isn't set,
    instead of silently returning empty AI results."""
    if not ai_service.is_configured():
        raise HTTPException(
            status_code=503,
            detail="AI features are off: OPENAI_API_KEY is not set on the server.",
        )


# Every AI endpoint needs the key; the rest of the CRM works without it.
router = APIRouter(dependencies=[Depends(require_openai_key)])
rules_engine = RulesEngine()


@router.post("/build-segment", response_model=BuildSegmentResponse)
async def build_segment(
    body: BuildSegmentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Convert plain-English prompt to segment rules + live preview."""
    rules_dict = await ai_service.build_segment_from_prompt(body.prompt)

    count = await rules_engine.count(db, rules_dict)
    sample = await rules_engine.sample(db, rules_dict, n=5)

    # Validate rules dict into SegmentRules schema
    try:
        rules_obj = SegmentRules(**rules_dict)
    except Exception:
        rules_obj = SegmentRules(operator="AND", conditions=[])

    return BuildSegmentResponse(
        rules=rules_obj,
        preview_count=count,
        sample_customers=[CustomerResponse.model_validate(c) for c in sample],
    )


@router.post("/write-message", response_model=WriteMessageResponse)
async def write_message(body: WriteMessageRequest):
    """Generate 3 message variants for a given segment and goal."""
    variants = await ai_service.write_message_variants(
        brand=body.brand_name,
        segment_desc=body.segment_description,
        channel=body.channel,
        goal=body.goal,
    )
    return WriteMessageResponse(
        variants=[MessageVariant(**v) for v in variants]
    )


@router.get("/insights/{campaign_id}", response_model=CampaignInsightsResponse)
async def campaign_insights(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Generate AI insights + recommendations for a campaign's performance."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Fetch segment rules
    segment_rules: dict = {}
    if campaign.segment_id:
        seg_result = await db.execute(
            select(Segment).where(Segment.id == campaign.segment_id)
        )
        segment = seg_result.scalar_one_or_none()
        if segment:
            segment_rules = segment.rules or {}

    # Build stats dict for the AI prompt — use cumulative IN() queries so that
    # messages that have progressed past a state still count toward earlier tiers.
    # (e.g. a "clicked" message is also counted as sent, delivered, and opened)
    SENT_STATUSES      = ["sent", "delivered", "opened", "read", "clicked", "converted"]
    DELIVERED_STATUSES = ["delivered", "opened", "read", "clicked", "converted"]
    OPENED_STATUSES    = ["opened", "read", "clicked", "converted"]
    CLICKED_STATUSES   = ["clicked", "converted"]
    CONVERTED_STATUSES = ["converted"]
    FAILED_STATUSES    = ["failed"]

    async def _count(statuses_list):
        """Count this campaign's messages whose status is in `statuses_list` (one funnel tier)."""
        r = await db.execute(
            select(func.count(Communication.id)).where(
                Communication.campaign_id == campaign_id,
                Communication.status.in_(statuses_list),
            )
        )
        return r.scalar_one()

    sent      = await _count(SENT_STATUSES)
    delivered = await _count(DELIVERED_STATUSES)
    failed    = await _count(FAILED_STATUSES)
    opened    = await _count(OPENED_STATUSES)
    clicked   = await _count(CLICKED_STATUSES)
    converted = await _count(CONVERTED_STATUSES)

    def safe_rate(n, d):
        """Return n/d as a 0-100 percentage rounded to 2 places, or 0.0 when d is 0."""
        return round(n / d * 100, 2) if d > 0 else 0.0

    stats = {
        "sent": sent,
        "delivered": delivered,
        "failed": failed,
        "opened": opened,
        "clicked": clicked,
        "converted": converted,
        "delivery_rate": safe_rate(delivered, sent + failed),
        "open_rate": safe_rate(opened, delivered),
        "click_rate": safe_rate(clicked, opened),
        "conversion_rate": safe_rate(converted, clicked),
    }

    raw_insights = await ai_service.get_campaign_insights(
        stats=stats,
        segment_rules=segment_rules,
        channel=campaign.channel,
    )

    return CampaignInsightsResponse(
        insights=[InsightItem(**i) for i in raw_insights]
    )


@router.post("/create-campaign", response_model=CreateCampaignResponse)
async def create_campaign_from_intent(
    body: CreateCampaignRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    One-shot campaign creator:
      1. AI builds segment rules from intent
      2. AI writes 3 message variants
      3. Segment + Campaign saved to DB (status=draft)
      4. Returns full campaign + segment + variants
    """
    ai_result = await ai_service.create_campaign_from_intent(body.intent)

    rules_dict = ai_result["rules"]
    variants = ai_result["message_variants"]

    # Validate rules
    try:
        rules_obj = SegmentRules(**rules_dict)
    except Exception:
        rules_obj = SegmentRules(operator="AND", conditions=[])

    # Compute customer count
    count = await rules_engine.count(db, rules_obj.model_dump())

    # Create Segment
    segment = Segment(
        name=f"AI Segment — {body.intent[:60]}",
        description=body.intent[:300],
        rules=rules_obj.model_dump(),
        ai_generated=True,
        customer_count=count,
    )
    db.add(segment)
    await db.commit()
    await db.refresh(segment)

    # Use first variant (friendly tone) as message template
    first_message = variants[0]["message"] if variants else body.intent

    # Create Campaign
    campaign = Campaign(
        name=f"AI Campaign — {body.intent[:80]}",
        segment_id=segment.id,
        channel="whatsapp",
        message_template=first_message,
        ai_generated_message=True,
        status="draft",
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    return CreateCampaignResponse(
        campaign=CampaignResponse.model_validate(campaign),
        segment=SegmentResponse.model_validate(segment),
        message_variants=[MessageVariant(**v) for v in variants],
        ready_to_launch=True,
    )
