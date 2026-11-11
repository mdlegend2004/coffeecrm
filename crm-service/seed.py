"""
seed.py — Populate the BrewCo CRM database with realistic sample data.

Run:  python seed.py
"""

import asyncio
import random
import uuid
from datetime import datetime, timedelta

from app.db.database import engine, AsyncSessionLocal, Base
from app.models.customer import Customer
from app.models.order import Order
from app.models.segment import Segment           # noqa: F401 — needed for mapper
from app.models.campaign import Campaign          # noqa: F401 — needed for mapper
from app.models.communication import Communication  # noqa: F401 — needed for mapper

# ── Sample data pools ─────────────────────────────────────────────────────────

FIRST_NAMES = [
    "Aarav", "Aditi", "Arjun", "Ananya", "Dev", "Diya", "Ishaan", "Kavya",
    "Krishna", "Meera", "Neha", "Nikhil", "Priya", "Rahul", "Rohan",
    "Saanvi", "Sahil", "Sneha", "Tanvi", "Varun", "Vikram", "Zara",
    "Amit", "Pooja", "Ravi", "Sonia", "Karan", "Nisha", "Manish", "Divya",
    "Aditya", "Anjali", "Gaurav", "Ritika", "Suresh", "Lakshmi", "Rajesh",
    "Deepika", "Sanjay", "Swati", "Harish", "Pallavi", "Vivek", "Shruti",
    "Akash", "Megha", "Tushar", "Preeti", "Kunal", "Simran",
]

LAST_NAMES = [
    "Sharma", "Patel", "Iyer", "Gupta", "Singh", "Reddy", "Nair", "Kumar",
    "Joshi", "Mehta", "Verma", "Choudhary", "Das", "Rao", "Pillai",
    "Banerjee", "Desai", "Kapoor", "Malhotra", "Bhat", "Agarwal", "Tiwari",
    "Shah", "Menon", "Chauhan", "Pandey", "Kulkarni", "Saxena", "Mishra", "Chopra",
]

CITIES = ["Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad", "Pune", "Kolkata"]

TAGS_POOL = [
    "loyal", "high-value", "churned", "new", "vip", "discount-seeker",
    "coffee-lover", "tea-lover", "snack-buyer", "weekend-regular",
    "morning-rush", "bulk-buyer", "festive-shopper", "referrer",
]

PRODUCTS = [
    ("Cold Brew Black", "beverage", 250),
    ("Cappuccino", "beverage", 200),
    ("Espresso Shot", "beverage", 150),
    ("Café Latte", "beverage", 220),
    ("Mocha Frappe", "beverage", 280),
    ("Matcha Latte", "beverage", 260),
    ("Filter Coffee", "beverage", 120),
    ("Masala Chai", "beverage", 100),
    ("Croissant", "food", 180),
    ("Paneer Sandwich", "food", 220),
    ("Chocolate Muffin", "food", 160),
    ("Blueberry Cheesecake", "food", 320),
    ("Veg Wrap", "food", 200),
    ("Chicken Puff", "food", 140),
    ("Brownie", "food", 190),
]

GENDERS = ["male", "female"]


def random_date(start_days_ago: int, end_days_ago: int) -> datetime:
    """Return a random datetime between `start_days_ago` and `end_days_ago` days before now."""
    days = random.randint(end_days_ago, start_days_ago)
    return datetime.utcnow() - timedelta(days=days)


async def seed():
    """Create tables if needed and fill the DB with sample customers and orders; used by build.sh on deploy."""
    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Check if data already exists
        from sqlalchemy import select, func
        result = await session.execute(select(func.count()).select_from(Customer))
        count = result.scalar()
        if count and count > 0:
            print(f"Database already has {count} customers. Skipping seed.")
            return

        customers = []
        all_orders = []

        for i in range(200):
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            name = f"{first} {last}"
            email = f"{first.lower()}.{last.lower()}{random.randint(1, 999)}@{'gmail.com' if random.random() > 0.3 else 'outlook.com'}"
            city = random.choice(CITIES)
            gender = random.choice(GENDERS)
            age = random.randint(18, 55)

            # Decide customer profile
            profile = random.choices(
                ["high-value", "regular", "low", "churned"],
                weights=[15, 40, 30, 15],
                k=1,
            )[0]

            if profile == "high-value":
                order_count = random.randint(8, 25)
                last_purchase_ago = random.randint(1, 30)
                tags = random.sample(["loyal", "high-value", "vip", "coffee-lover", "bulk-buyer"], k=random.randint(2, 4))
            elif profile == "regular":
                order_count = random.randint(3, 10)
                last_purchase_ago = random.randint(5, 90)
                tags = random.sample(["coffee-lover", "snack-buyer", "weekend-regular", "morning-rush"], k=random.randint(1, 3))
            elif profile == "churned":
                order_count = random.randint(1, 5)
                last_purchase_ago = random.randint(90, 365)
                tags = ["churned"] + random.sample(["discount-seeker", "tea-lover"], k=random.randint(0, 1))
            else:  # low
                order_count = random.randint(1, 3)
                last_purchase_ago = random.randint(10, 180)
                tags = random.sample(["new", "discount-seeker", "festive-shopper"], k=random.randint(1, 2))

            customer_id = uuid.uuid4()
            total_spent = 0.0
            last_purchase_date = datetime.utcnow() - timedelta(days=last_purchase_ago)

            # Generate orders
            for j in range(order_count):
                product_name, product_category, base_price = random.choice(PRODUCTS)
                amount = round(base_price * random.uniform(0.8, 1.5), 2)
                total_spent += amount
                status = random.choices(["completed", "returned", "pending"], weights=[85, 8, 7], k=1)[0]

                order_date = random_date(365, last_purchase_ago) if j < order_count - 1 else last_purchase_date

                order = Order(
                    id=uuid.uuid4(),
                    customer_id=customer_id,
                    amount=amount,
                    product_name=product_name,
                    product_category=product_category,
                    status=status,
                    ordered_at=order_date,
                )
                all_orders.append(order)

            total_spent = round(total_spent, 2)

            customer = Customer(
                id=customer_id,
                name=name,
                email=email,
                phone=f"+91{random.randint(7000000000, 9999999999)}",
                city=city,
                gender=gender,
                age=age,
                total_spent=total_spent,
                purchase_count=order_count,
                last_purchase_date=last_purchase_date,
                tags=tags,
                created_at=random_date(365, 1),
            )
            customers.append(customer)

        session.add_all(customers)
        session.add_all(all_orders)
        await session.commit()

        print(f"✅ Seeded {len(customers)} customers and {len(all_orders)} orders.")


if __name__ == "__main__":
    asyncio.run(seed())
