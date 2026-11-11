"""
api/routes/analytics.py — Aggregate analytics endpoints.

GET /overview  — top-level KPIs for the dashboard
GET /campaigns — all campaigns with full stats
"""

from __future__ import annotations
from datetime import datetime, UTC

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.campaign import Campaign
from app.models.communication import Communication
from app.models.customer import Customer

router = APIRouter()


@router.get("/overview")
async def analytics_overview(db: AsyncSession = Depends(get_db)):
    """
    Dashboard KPIs:
      - total_customers
      - campaigns_this_month
      - avg_delivery_rate (across completed campaigns)
      - top_channel (channel with most campaigns)
    """
    # Total customers
    cust_result = await db.execute(select(func.count(Customer.id)))
    total_customers = cust_result.scalar_one()

    # Campaigns created this calendar month
    now = datetime.now(UTC).replace(tzinfo=None)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_result = await db.execute(
        select(func.count(Campaign.id)).where(Campaign.created_at >= month_start)
    )
    campaigns_this_month = month_result.scalar_one()

    # Avg delivery rate — only for completed campaigns that have sent messages
    campaigns_result = await db.execute(
        select(Campaign).where(Campaign.status == "completed")
    )
    completed = campaigns_result.scalars().all()

    delivery_rates = []
    for campaign in completed:
        sent_r = await db.execute(
            select(func.count(Communication.id)).where(
                Communication.campaign_id == campaign.id,
                Communication.status.in_(["sent", "delivered", "opened", "read", "clicked", "converted"]),
            )
        )
        sent = sent_r.scalar_one()

        delivered_r = await db.execute(
            select(func.count(Communication.id)).where(
                Communication.campaign_id == campaign.id,
                Communication.status.in_(["delivered", "opened", "read", "clicked", "converted"]),
            )
        )
        delivered = delivered_r.scalar_one()

        failed_r = await db.execute(
            select(func.count(Communication.id)).where(
                Communication.campaign_id == campaign.id,
                Communication.status == "failed",
            )
        )
        attempted = sent + failed_r.scalar_one()

        if attempted > 0:
            delivery_rates.append(delivered / attempted * 100)

    avg_delivery_rate = round(sum(delivery_rates) / len(delivery_rates), 2) if delivery_rates else 0.0

    # Top channel by campaign count
    channel_result = await db.execute(
        select(Campaign.channel, func.count(Campaign.id).label("cnt"))
        .group_by(Campaign.channel)
        .order_by(func.count(Campaign.id).desc())
        .limit(1)
    )
    top_row = channel_result.first()
    top_channel = top_row[0] if top_row else None

    return {
        "total_customers": total_customers,
        "campaigns_this_month": campaigns_this_month,
        "avg_delivery_rate": avg_delivery_rate,
        "top_channel": top_channel,
    }


@router.get("/campaigns")
async def analytics_campaigns(db: AsyncSession = Depends(get_db)):
    """All campaigns with full delivery funnel stats."""
    result = await db.execute(select(Campaign).order_by(Campaign.created_at.desc()))
    campaigns = result.scalars().all()

    # Funnel tiers — each includes all statuses that represent "at least this far"
    # (mirrors the same fix already in campaigns.py _get_campaign_stats)
    SENT_STATUSES      = ["sent", "delivered", "opened", "read", "clicked", "converted"]
    DELIVERED_STATUSES = ["delivered", "opened", "read", "clicked", "converted"]
    OPENED_STATUSES    = ["opened", "read", "clicked", "converted"]
    CLICKED_STATUSES   = ["clicked", "converted"]
    CONVERTED_STATUSES = ["converted"]
    FAILED_STATUSES    = ["failed"]

    def safe_rate(n, d):
        """Return n/d as a 0-100 percentage rounded to 2 places, or 0.0 when d is 0."""
        return round(n / d * 100, 2) if d > 0 else 0.0

    async def _count(campaign_id, statuses_list):
        """Count one campaign's messages whose status is in `statuses_list` (one funnel tier)."""
        r = await db.execute(
            select(func.count(Communication.id)).where(
                Communication.campaign_id == campaign_id,
                Communication.status.in_(statuses_list),
            )
        )
        return r.scalar_one()

    stats = []
    for campaign in campaigns:
        sent      = await _count(campaign.id, SENT_STATUSES)
        delivered = await _count(campaign.id, DELIVERED_STATUSES)
        failed    = await _count(campaign.id, FAILED_STATUSES)
        opened    = await _count(campaign.id, OPENED_STATUSES)
        clicked   = await _count(campaign.id, CLICKED_STATUSES)
        converted = await _count(campaign.id, CONVERTED_STATUSES)

        stats.append({
            "campaign_id": str(campaign.id),
            "name": campaign.name,
            "channel": campaign.channel,
            "status": campaign.status,
            "created_at": campaign.created_at.isoformat(),
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
        })

    return stats
