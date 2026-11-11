"""
services/segmentation.py — Dynamic SQLAlchemy filter builder (RulesEngine).

Design:
  The rules dict has shape: { "operator": "AND"|"OR", "conditions": [...] }
  Each condition: { "field": str, "op": str, "value": any }

  _build_filters() maps field names → model columns and op strings →
  SQLAlchemy operators. This keeps all filter logic in one place so
  adding a new field or operator only requires editing this file.

  Async methods (count/get_ids/sample) are awaited from routes so they
  don't block the event loop on large customer tables.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, List
from uuid import UUID

from sqlalchemy import and_, or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.customer import Customer


class RulesEngine:
    """Turns a segment's JSON rules into SQL WHERE clauses and runs count / id / sample queries."""
    # Map rule field names → Customer model attributes
    FIELD_MAP = {
        "total_spent": Customer.total_spent,
        "purchase_count": Customer.purchase_count,
        "last_purchase_date": Customer.last_purchase_date,
        "city": Customer.city,
        "age": Customer.age,
        "gender": Customer.gender,
        "tags": Customer.tags,
    }

    # Fields that should use case-insensitive comparison
    STRING_FIELDS = {"city", "gender"}
    # Fields that must be compared as numbers
    NUMERIC_FIELDS = {"total_spent", "purchase_count", "age"}

    def _coerce_value(self, field_name: str, value: Any) -> Any:
        """Coerce value to the correct type for the given field."""
        if field_name in self.NUMERIC_FIELDS:
            try:
                if field_name == "purchase_count" or field_name == "age":
                    return int(value)
                return float(value)
            except (ValueError, TypeError):
                return value
        return value

    def _build_filters(self, conditions: list, operator: str) -> Any:
        """
        Convert a list of SegmentCondition dicts into SQLAlchemy filter clauses.

        Supported ops:
          eq, neq, gte, lte, gt, lt       — standard comparisons
          in, not_in                       — list membership
          days_ago_lte, days_ago_gte       — date-relative ("active in last N days")
          contains                         — Postgres ARRAY contains value

        String fields (city, gender) use case-insensitive matching via LOWER().
        Numeric values are coerced from strings when needed.
        """
        filters = []

        for cond in conditions:
            field_name = cond.get("field") if isinstance(cond, dict) else cond.field
            op = cond.get("op") if isinstance(cond, dict) else cond.op
            value = cond.get("value") if isinstance(cond, dict) else cond.value

            col = self.FIELD_MAP.get(field_name)
            if col is None:
                continue  # unknown field — skip gracefully

            is_string = field_name in self.STRING_FIELDS
            value = self._coerce_value(field_name, value)

            if op == "eq":
                if is_string and isinstance(value, str):
                    filters.append(func.lower(col) == value.lower())
                else:
                    filters.append(col == value)
            elif op == "neq":
                if is_string and isinstance(value, str):
                    filters.append(func.lower(col) != value.lower())
                else:
                    filters.append(col != value)
            elif op == "gte":
                filters.append(col >= value)
            elif op == "lte":
                filters.append(col <= value)
            elif op == "gt":
                filters.append(col > value)
            elif op == "lt":
                filters.append(col < value)
            elif op == "in":
                vals = value if isinstance(value, list) else [value]
                if is_string:
                    vals = [v.lower() if isinstance(v, str) else v for v in vals]
                    filters.append(func.lower(col).in_(vals))
                else:
                    filters.append(col.in_(vals))
            elif op == "not_in":
                vals = value if isinstance(value, list) else [value]
                if is_string:
                    vals = [v.lower() if isinstance(v, str) else v for v in vals]
                    filters.append(func.lower(col).not_in(vals))
                else:
                    filters.append(col.not_in(vals))
            elif op == "days_ago_lte":
                # "active in last N days" → last_purchase_date >= now - N days
                cutoff = datetime.utcnow() - timedelta(days=int(value))
                filters.append(col >= cutoff)
            elif op == "days_ago_gte":
                # "inactive for N+ days" → last_purchase_date <= now - N days
                cutoff = datetime.utcnow() - timedelta(days=int(value))
                filters.append(col <= cutoff)
            elif op == "contains":
                # Postgres ARRAY @> [value] — customer has this tag
                if isinstance(value, str):
                    filters.append(col.contains([value.lower()]))
                else:
                    filters.append(col.contains([value]))

        if not filters:
            return None

        return and_(*filters) if operator.upper() == "AND" else or_(*filters)

    def _base_query(self, rules: dict):
        """Build a base SELECT on Customer with rules applied."""
        operator = rules.get("operator", "AND")
        conditions = rules.get("conditions", [])
        where_clause = self._build_filters(conditions, operator)

        stmt = select(Customer)
        if where_clause is not None:
            stmt = stmt.where(where_clause)
        return stmt

    async def count(self, db: AsyncSession, rules: dict) -> int:
        """Return count of customers matching the rules."""
        operator = rules.get("operator", "AND")
        conditions = rules.get("conditions", [])
        where_clause = self._build_filters(conditions, operator)

        stmt = select(func.count()).select_from(Customer)
        if where_clause is not None:
            stmt = stmt.where(where_clause)

        result = await db.execute(stmt)
        return result.scalar_one()

    async def get_ids(self, db: AsyncSession, rules: dict) -> List[UUID]:
        """Return list of customer UUIDs matching the rules."""
        stmt = self._base_query(rules).with_only_columns(Customer.id)
        result = await db.execute(stmt)
        return [row[0] for row in result.fetchall()]

    async def sample(self, db: AsyncSession, rules: dict, n: int = 5) -> List[Customer]:
        """Return up to n Customer objects matching the rules."""
        stmt = self._base_query(rules).options(selectinload(Customer.orders)).limit(n)
        result = await db.execute(stmt)
        return list(result.scalars().all())


# ── Quick smoke test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    from app.db.database import AsyncSessionLocal

    async def _test():
        """Manual smoke test: print how many big spenders live in Mumbai or Delhi."""
        rules = {
            "operator": "AND",
            "conditions": [
                {"field": "total_spent", "op": "gte", "value": 5000},
                {"field": "city", "op": "in", "value": ["Mumbai", "Delhi"]},
            ],
        }
        async with AsyncSessionLocal() as db:
            engine = RulesEngine()
            count = await engine.count(db, rules)
            print(f"Matching customers: {count}")
            sample = await engine.sample(db, rules, n=3)
            for c in sample:
                print(f"  {c.name} | {c.city} | ₹{c.total_spent:.0f}")

    asyncio.run(_test())
