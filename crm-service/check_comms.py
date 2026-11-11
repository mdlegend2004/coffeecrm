"""Quick diagnostic: check Communication statuses for recent campaigns."""
import asyncio
from app.db.database import AsyncSessionLocal
from sqlalchemy import select, func, text

# Import ALL models so SQLAlchemy relationships resolve correctly
from app.models.customer import Customer
from app.models.segment import Segment
from app.models.campaign import Campaign
from app.models.communication import Communication


async def check():
    """Print message status counts for the most recent campaigns (debugging helper)."""
    async with AsyncSessionLocal() as db:
        # Raw count from DB
        raw = await db.execute(text("SELECT status, count(*) FROM communications GROUP BY status"))
        print("=== RAW communication status counts ===")
        for row in raw.all():
            print(f"  {row[0]}: {row[1]}")

        print()

        r = await db.execute(select(Campaign).order_by(Campaign.created_at.desc()).limit(5))
        campaigns = r.scalars().all()
        if not campaigns:
            print("No campaigns found!")
            return

        for c in campaigns:
            print(f"\nCampaign: {c.name}")
            print(f"  status: {c.status} | id: {c.id}")
            print(f"  segment_id: {c.segment_id}")

            cr = await db.execute(
                select(Communication.status, func.count(Communication.id))
                .where(Communication.campaign_id == c.id)
                .group_by(Communication.status)
            )
            rows = cr.all()
            if not rows:
                print("  NO Communications found for this campaign!")
            for status, count in rows:
                print(f"  {status}: {count}")

            total = await db.execute(
                select(func.count(Communication.id))
                .where(Communication.campaign_id == c.id)
            )
            print(f"  TOTAL comms: {total.scalar_one()}")

            # Check a sample communication
            sample = await db.execute(
                select(Communication)
                .where(Communication.campaign_id == c.id)
                .limit(2)
            )
            for comm in sample.scalars().all():
                print(f"  Sample: ext_id={comm.external_id} status={comm.status} sent_at={comm.sent_at} delivered_at={comm.delivered_at}")


asyncio.run(check())
