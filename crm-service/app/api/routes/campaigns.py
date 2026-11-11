"""
api/routes/campaigns.py — Campaign management endpoints.

GET /          — list all campaigns
POST /         — create draft campaign
POST /{id}/launch — launch campaign (BackgroundTasks)
GET /{id}      — campaign detail
GET /{id}/stats — delivery funnel stats with rates
"""

from __future__ import annotations
import asyncio
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db, AsyncSessionLocal
from app.models.campaign import Campaign
from app.models.communication import Communication
from app.schemas.campaign import (
    CampaignCreate,
    CampaignResponse,
    CampaignStatsResponse,
)
from app.services.campaign_service import launch_campaign

router = APIRouter()

_background_tasks: set[asyncio.Task] = set()


def _safe_rate(numerator: int, denominator: int) -> float:
    """Division-by-zero safe rate calculation (0–100 scale)."""
    return round(numerator / denominator * 100, 2) if denominator > 0 else 0.0


async def _get_campaign_stats(campaign: Campaign, db: AsyncSession) -> CampaignStatsResponse:
    """
    Shared helper: count communications by status and compute rates.

    Status is a linear funnel: queued → sent → delivered → opened → clicked → converted.
    A message at 'opened' has also been 'sent' and 'delivered', so we count
    each tier cumulatively using IN() with all downstream statuses.
    This gives accurate funnel rates even as messages progress through states.
    """
    # Funnel tiers — each includes all statuses that represent "at least this far"
    SENT_STATUSES     = ["sent", "delivered", "opened", "read", "clicked", "converted"]
    DELIVERED_STATUSES = ["delivered", "opened", "read", "clicked", "converted"]
    OPENED_STATUSES   = ["opened", "read", "clicked", "converted"]
    CLICKED_STATUSES  = ["clicked", "converted"]
    CONVERTED_STATUSES = ["converted"]
    FAILED_STATUSES   = ["failed"]

    async def _count(statuses_list):
        """Count this campaign's messages whose status is in `statuses_list` (one funnel tier)."""
        r = await db.execute(
            select(func.count(Communication.id)).where(
                Communication.campaign_id == campaign.id,
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

    return CampaignStatsResponse(
        campaign_id=campaign.id,
        name=campaign.name,
        channel=campaign.channel,
        status=campaign.status,
        sent=sent,
        delivered=delivered,
        failed=failed,
        opened=opened,
        clicked=clicked,
        converted=converted,
        delivery_rate=_safe_rate(delivered, sent + failed),
        open_rate=_safe_rate(opened, delivered),
        click_rate=_safe_rate(clicked, opened),
        conversion_rate=_safe_rate(converted, clicked),
    )


@router.get("/", response_model=List[CampaignResponse])
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    """GET /api/campaigns — every campaign, newest first (no stats; see /api/analytics/campaigns for those)."""
    result = await db.execute(select(Campaign).order_by(Campaign.created_at.desc()))
    return [CampaignResponse.model_validate(c) for c in result.scalars().all()]


@router.post("/", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    body: CampaignCreate,
    db: AsyncSession = Depends(get_db),
):
    """POST /api/campaigns — save a new campaign as a draft. Nothing is sent until /launch is called."""
    campaign = Campaign(
        name=body.name,
        segment_id=body.segment_id,
        channel=body.channel,
        message_template=body.message_template,
        ai_generated_message=body.ai_generated_message,
        status="draft",
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return CampaignResponse.model_validate(campaign)


async def _run_campaign_background(campaign_id: UUID):
    """
    BackgroundTasks wrapper: creates its own DB session since FastAPI's
    request session is closed when the response is sent.
    This is the canonical pattern for background DB work in async FastAPI.
    """
    async with AsyncSessionLocal() as db:
        await launch_campaign(campaign_id, db)


@router.post("/{campaign_id}/launch")
async def launch_campaign_endpoint(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Launch a draft campaign.
    Returns immediately; actual sending happens as an asyncio task.
    The task uses its OWN session (not the request session).
    """
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status != "draft":
        raise HTTPException(
            status_code=400,
            detail=f"Campaign is already {campaign.status} — only drafts can be launched",
        )

    # Claim the campaign before spawning the task so a second click can't
    # launch it twice.
    campaign.status = "running"
    await db.commit()

    task = asyncio.create_task(_run_campaign_background(campaign_id))
    _background_tasks.add(task)  # keep a strong ref so it isn't GC'd mid-run
    task.add_done_callback(_background_tasks.discard)
    return {"message": "Campaign launched", "campaign_id": str(campaign_id)}


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """GET /api/campaigns/{id} — one campaign's fields, or 404 if it doesn't exist."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignResponse.model_validate(campaign)


@router.get("/{campaign_id}/stats", response_model=CampaignStatsResponse)
async def get_campaign_stats(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """GET /api/campaigns/{id}/stats — delivery funnel counts and rates; the detail page polls this every 4s."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return await _get_campaign_stats(campaign, db)
