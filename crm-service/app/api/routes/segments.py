"""
api/routes/segments.py — Segment management endpoints.

GET /              — list all segments
POST /             — create + compute customer_count
POST /preview      — preview without saving (count + sample)
GET /{id}/customers — paginated customers matching segment rules
DELETE /{id}       — hard delete
"""

from __future__ import annotations
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.segment import Segment
from app.models.customer import Customer
from app.schemas.segment import (
    SegmentCreate,
    SegmentResponse,
    SegmentPreviewResponse,
    SegmentRules,
)
from app.schemas.customer import CustomerResponse, CustomerListResponse
from app.services.segmentation import RulesEngine

router = APIRouter()
rules_engine = RulesEngine()


@router.get("/", response_model=List[SegmentResponse])
async def list_segments(db: AsyncSession = Depends(get_db)):
    """GET /api/segments — every saved segment, newest first, with its cached customer_count."""
    result = await db.execute(select(Segment).order_by(Segment.created_at.desc()))
    return [SegmentResponse.model_validate(s) for s in result.scalars().all()]


@router.post("/", response_model=SegmentResponse, status_code=201)
async def create_segment(
    body: SegmentCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create segment, then immediately compute and cache customer_count.
    Caching avoids expensive counts on every list request.
    """
    segment = Segment(
        name=body.name,
        description=body.description,
        rules=body.rules.model_dump(),
        ai_generated=body.ai_generated,
    )
    db.add(segment)
    await db.commit()

    # Compute and cache count
    count = await rules_engine.count(db, segment.rules)
    segment.customer_count = count
    await db.commit()
    await db.refresh(segment)

    return SegmentResponse.model_validate(segment)


@router.post("/preview", response_model=SegmentPreviewResponse)
async def preview_segment(
    body: SegmentRules,
    db: AsyncSession = Depends(get_db),
):
    """Preview segment without saving to DB — safe for iterative rule building.

    Body is just the rules ({"operator": ..., "conditions": [...]}) — a preview
    has no name, and this is exactly what the frontend's previewSegment() sends.
    """
    rules_dict = body.model_dump()
    count = await rules_engine.count(db, rules_dict)
    sample = await rules_engine.sample(db, rules_dict, n=5)

    return SegmentPreviewResponse(
        count=count,
        sample_customers=[CustomerResponse.model_validate(c) for c in sample],
    )


@router.get("/{segment_id}/customers", response_model=CustomerListResponse)
async def segment_customers(
    segment_id: UUID,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of customers matching this segment's rules."""
    result = await db.execute(select(Segment).where(Segment.id == segment_id))
    segment = result.scalar_one_or_none()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    # Build base query from rules
    operator = segment.rules.get("operator", "AND")
    conditions = segment.rules.get("conditions", [])
    where_clause = rules_engine._build_filters(conditions, operator)

    from sqlalchemy import func
    count_stmt = select(func.count()).select_from(Customer)
    if where_clause is not None:
        count_stmt = count_stmt.where(where_clause)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = select(Customer).options(selectinload(Customer.orders))
    if where_clause is not None:
        stmt = stmt.where(where_clause)
    stmt = stmt.offset((page - 1) * limit).limit(limit)
    customers_result = await db.execute(stmt)
    customers = customers_result.scalars().all()

    return CustomerListResponse(
        items=[CustomerResponse.model_validate(c) for c in customers],
        total=total,
        page=page,
        limit=limit,
    )


@router.delete("/{segment_id}", status_code=204)
async def delete_segment(
    segment_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """DELETE /api/segments/{id} — hard-delete a segment (404 if missing).

    Campaigns that used it keep existing but their segment_id becomes NULL,
    so a draft campaign whose segment was deleted will fail when launched."""
    result = await db.execute(select(Segment).where(Segment.id == segment_id))
    segment = result.scalar_one_or_none()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    await db.delete(segment)
    await db.commit()
