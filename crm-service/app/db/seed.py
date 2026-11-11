"""
db/seed.py — Seed 200 customers + 600 orders into the brewco database.

Run from inside crm-service/:
    python -m app.db.seed

Design:
  - Faker locale="en_IN" gives Indian names, phone numbers, emails
    that match the BrewCo coffee chain India context.
  - Orders are weighted toward high purchase_count customers to reflect
    real CRM data skew (loyal customers have more order history).
  - total_spent and purchase_count are recomputed from completed orders
    after all inserts, ensuring derived fields are consistent with raw data.
  - Emails are deduplicated with a set to avoid unique constraint violations.
"""

from __future__ import annotations
import asyncio
import random
from datetime import datetime, timedelta

from faker import Faker
from sqlalchemy import text

from app.db.database import AsyncSessionLocal, engine, Base
from app.models.customer import Customer
from app.models.order import Order
# Import remaining models so SQLAlchemy relationship resolver finds them all
from app.models.segment import Segment          # noqa: F401
from app.models.campaign import Campaign        # noqa: F401
from app.models.communication import Communication  # noqa: F401

fake = Faker("en_IN")
random.seed(42)

CITIES = ["Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad", "Pune", "Kolkata"]
GENDERS = ["M", "F", "Other"]
TAGS_POOL = ["loyal", "vip", "new", "at-risk", "lapsed", "weekend-visitor"]

PRODUCTS = [
    ("Espresso", "beverage"),
    ("Cold Brew", "beverage"),
    ("Cappuccino", "beverage"),
    ("Latte", "beverage"),
    ("Mocha", "beverage"),
    ("Filter Coffee", "beverage"),
    ("Matcha Latte", "beverage"),
    ("Chai Latte", "beverage"),
    ("Croissant", "food"),
    ("Sandwich", "food"),
]

ORDER_STATUSES = ["completed", "returned", "pending"]
ORDER_WEIGHTS = [85, 10, 5]

NUM_CUSTOMERS = 200
NUM_ORDERS = 600


async def seed():
    """Insert 200 fake Indian customers and 600 orders, then recompute each customer's totals from completed orders."""
    print("[SEED] Starting seed...")

    async with AsyncSessionLocal() as db:
        # ── Create customers ─────────────────────────────────────────────────
        customers: list[Customer] = []
        used_emails: set[str] = set()

        for _ in range(NUM_CUSTOMERS):
            # Ensure unique email
            email = fake.email()
            attempts = 0
            while email in used_emails and attempts < 10:
                email = fake.email()
                attempts += 1
            used_emails.add(email)

            purchase_count = random.randint(1, 50)
            last_purchase_date = datetime.utcnow() - timedelta(
                days=random.randint(0, 540)
            )
            tags = random.sample(TAGS_POOL, k=random.randint(0, 2))

            customer = Customer(
                name=fake.name(),
                email=email,
                phone=fake.phone_number()[:20],
                city=random.choice(CITIES),
                gender=random.choice(GENDERS),
                age=random.randint(18, 55),
                purchase_count=purchase_count,
                total_spent=round(random.uniform(500, 50000), 2),
                last_purchase_date=last_purchase_date,
                tags=tags if tags else None,
            )
            customers.append(customer)
            db.add(customer)

        await db.commit()
        print(f"[SEED] Inserted {len(customers)} customers")

        # Refresh to get generated IDs
        for c in customers:
            await db.refresh(c)

        # ── Create orders ────────────────────────────────────────────────────
        # Weight customers by purchase_count so heavy buyers get more orders
        weights = [c.purchase_count for c in customers]
        total_weight = sum(weights)
        probs = [w / total_weight for w in weights]

        orders: list[Order] = []
        for _ in range(NUM_ORDERS):
            # Pick customer weighted by purchase_count
            customer = random.choices(customers, weights=probs, k=1)[0]

            product_name, product_category = random.choice(PRODUCTS)
            status = random.choices(ORDER_STATUSES, weights=ORDER_WEIGHTS, k=1)[0]

            # Order date is within 180 days before last_purchase_date
            days_before = random.randint(0, 180)
            ordered_at = customer.last_purchase_date - timedelta(days=days_before)

            order = Order(
                customer_id=customer.id,
                amount=round(random.uniform(80, 800), 2),
                product_name=product_name,
                product_category=product_category,
                status=status,
                ordered_at=ordered_at,
            )
            orders.append(order)
            db.add(order)

        await db.commit()
        print(f"[SEED] Inserted {len(orders)} orders")

        # ── Recompute total_spent and purchase_count from completed orders ───
        print("[SEED] Recomputing customer totals from completed orders...")
        for customer in customers:
            completed = [
                o for o in orders
                if o.customer_id == customer.id and o.status == "completed"
            ]
            customer.total_spent = round(sum(o.amount for o in completed), 2)
            customer.purchase_count = len(completed)

        await db.commit()
        print("[SEED] Customer totals updated")
        print(f"\n[SEED] COMPLETE! {NUM_CUSTOMERS} customers, {NUM_ORDERS} orders in brewco DB.")


if __name__ == "__main__":
    asyncio.run(seed())
