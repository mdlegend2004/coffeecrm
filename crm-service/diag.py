"""Diagnostic: raw SQL only, no ORM models needed."""
import asyncio
from app.db.database import AsyncSessionLocal
from sqlalchemy import text


async def check():
    """Print raw-SQL status breakdowns of communications and campaigns (debugging helper)."""
    async with AsyncSessionLocal() as db:
        # 1. Overall communication status distribution
        r = await db.execute(text("SELECT status, count(*) FROM communications GROUP BY status ORDER BY count(*) DESC"))
        print("=== ALL communication statuses ===")
        for row in r.all():
            print(f"  {row[0]}: {row[1]}")

        # 2. Per-campaign breakdown
        r = await db.execute(text("""
            SELECT c.id, c.name, c.status, c.channel,
                   count(co.id) as total_comms,
                   count(co.id) FILTER (WHERE co.status IN ('sent','delivered','opened','read','clicked','converted')) as sent_count,
                   count(co.id) FILTER (WHERE co.status IN ('delivered','opened','read','clicked','converted')) as delivered_count,
                   count(co.id) FILTER (WHERE co.status IN ('opened','read','clicked','converted')) as opened_count,
                   count(co.id) FILTER (WHERE co.status IN ('clicked','converted')) as clicked_count,
                   count(co.id) FILTER (WHERE co.status = 'converted') as converted_count,
                   count(co.id) FILTER (WHERE co.status = 'failed') as failed_count
            FROM campaigns c
            LEFT JOIN communications co ON co.campaign_id = c.id
            GROUP BY c.id, c.name, c.status, c.channel
            ORDER BY c.created_at DESC
            LIMIT 5
        """))
        print("\n=== Per-campaign stats (what the API should return) ===")
        for row in r.all():
            cid, name, status, channel, total, sent, delivered, opened, clicked, converted, failed = row
            print(f"\nCampaign: {name}")
            print(f"  id={cid} status={status} channel={channel}")
            print(f"  total={total} sent={sent} delivered={delivered} opened={opened} clicked={clicked} converted={converted} failed={failed}")
            if sent > 0:
                print(f"  delivery_rate={round(delivered/sent*100,2)}%")
            if delivered > 0:
                print(f"  open_rate={round(opened/delivered*100,2)}%")
            if opened > 0:
                print(f"  click_rate={round(clicked/opened*100,2)}%")

        # 3. Check a sample communication to see timestamps
        r = await db.execute(text("""
            SELECT external_id, status, sent_at, delivered_at, opened_at, clicked_at, converted_at
            FROM communications
            WHERE status != 'queued'
            LIMIT 5
        """))
        print("\n=== Sample communications ===")
        for row in r.all():
            print(f"  ext={row[0]} status={row[1]} sent={row[2]} deliv={row[3]} opened={row[4]} clicked={row[5]} conv={row[6]}")

        # 4. Test the API endpoint directly via HTTP
        print("\n=== Testing /api/campaigns/ endpoint ===")
        r = await db.execute(text("SELECT id FROM campaigns ORDER BY created_at DESC LIMIT 1"))
        row = r.first()
        if row:
            campaign_id = row[0]
            print(f"  Latest campaign ID: {campaign_id}")
            print(f"  Test URL: http://localhost:8000/api/campaigns/{campaign_id}/stats")


asyncio.run(check())
