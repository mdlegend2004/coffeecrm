import asyncio
from app.db.database import AsyncSessionLocal
from sqlalchemy import select, func
from app.models.customer import Customer

async def check():
    """Print customer counts per city, spend ranges, and case-sensitivity checks (debugging helper)."""
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(func.count()).select_from(Customer))
        print(f"Total customers: {r.scalar_one()}")

        r = await db.execute(select(Customer.city, func.count(Customer.id)).group_by(Customer.city))
        print("Cities:", dict(r.fetchall()))

        r = await db.execute(
            select(func.min(Customer.total_spent), func.max(Customer.total_spent), func.avg(Customer.total_spent)).select_from(Customer)
        )
        mn, mx, av = r.fetchone()
        print(f"Spent: min={mn}, max={mx}, avg={av:.0f}")

        # Case-sensitive check
        r = await db.execute(
            select(func.count()).select_from(Customer).where(Customer.city == "Mumbai", Customer.total_spent > 1000)
        )
        print(f"Mumbai (capitalized) + spent>1000: {r.scalar_one()}")

        r = await db.execute(
            select(func.count()).select_from(Customer).where(Customer.city == "mumbai", Customer.total_spent > 1000)
        )
        print(f"mumbai (lowercase) + spent>1000: {r.scalar_one()}")

        # Show a few Mumbai customers
        r = await db.execute(
            select(Customer.name, Customer.city, Customer.total_spent)
            .where(Customer.city == "Mumbai")
            .limit(5)
        )
        print("Sample Mumbai customers:")
        for row in r.fetchall():
            print(f"  {row[0]} | {row[1]} | {row[2]}")

asyncio.run(check())
