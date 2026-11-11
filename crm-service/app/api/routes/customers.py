"""
api/routes/customers.py — Customer CRUD endpoints.

GET /    — paginated list with optional filters
POST /   — create single customer
POST /bulk — bulk insert
GET /{id} — customer detail with last 10 orders
"""

from __future__ import annotations
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.customer import Customer
from app.models.order import Order
from app.schemas.customer import (
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
)

router = APIRouter()


@router.get("/", response_model=CustomerListResponse)
async def list_customers(
    city: Optional[str] = None,
    min_spent: Optional[float] = None,
    max_spent: Optional[float] = None,
    search: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Paginated customer list with optional filters.
    search matches against name OR email (case-insensitive).
    """
    stmt = select(Customer)

    if city:
        stmt = stmt.where(Customer.city == city)
    if min_spent is not None:
        stmt = stmt.where(Customer.total_spent >= min_spent)
    if max_spent is not None:
        stmt = stmt.where(Customer.total_spent <= max_spent)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Customer.name.ilike(pattern),
                Customer.email.ilike(pattern),
            )
        )

    # Total count (without pagination)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Paginated results
    offset = (page - 1) * limit
    stmt = stmt.offset(offset).limit(limit).order_by(Customer.created_at.desc())
    result = await db.execute(stmt)
    customers = result.scalars().all()

    return CustomerListResponse(
        items=[
            CustomerResponse.from_customer(c)
            for c in customers
        ],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("/", response_model=CustomerResponse, status_code=201)
async def create_customer(
    body: CustomerCreate,
    db: AsyncSession = Depends(get_db),
):
    """POST /api/customers — insert one customer. Returns 409 if the email is already taken."""
    customer = Customer(**body.model_dump())
    db.add(customer)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"A customer with email {body.email} already exists")
    await db.refresh(customer)
    return CustomerResponse.from_customer(customer)


@router.post("/bulk", status_code=201)
async def bulk_create_customers(
    body: List[CustomerCreate],
    db: AsyncSession = Depends(get_db),
):
    """Bulk insert customers. Returns count inserted."""
    customers = [Customer(**c.model_dump()) for c in body]
    db.add_all(customers)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="One or more emails already exist (or are duplicated in the batch); nothing was inserted")
    return {"inserted": len(customers)}


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Customer detail with last 10 orders ordered by ordered_at desc."""
    result = await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Fetch last 10 orders separately to control ordering
    orders_result = await db.execute(
        select(Order)
        .where(Order.customer_id == customer_id)
        .order_by(Order.ordered_at.desc())
        .limit(10)
    )
    orders = orders_result.scalars().all()

    return CustomerResponse.from_customer(customer, orders=orders)
