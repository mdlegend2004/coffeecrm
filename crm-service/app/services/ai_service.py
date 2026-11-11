"""
services/ai_service.py — OpenAI gpt-4o-mini integration.

Design:
  - All calls use the async OpenAI client (AsyncOpenAI) so they don't
    block the FastAPI event loop during long LLM responses.
  - System prompts enforce JSON-only output — no markdown, no backticks.
    This keeps parsing simple and avoids the common ```json ... ``` wrapping.
  - JSON parse errors are caught and a safe fallback is returned so the
    API never 500s due to a malformed LLM response.
  - gpt-4o-mini is used for all calls — cost-effective and fast enough
    for CRM use cases.
"""

from __future__ import annotations
import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

logger = logging.getLogger(__name__)

# The client is created on first use, not at import time: the OpenAI SDK raises
# if the key is missing, and that would stop the whole app from starting.
_client: AsyncOpenAI | None = None


def is_configured() -> bool:
    """True when OPENAI_API_KEY is set, i.e. the AI features can be used."""
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def _get_client() -> AsyncOpenAI:
    """Return the shared OpenAI client, creating it the first time it's needed."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "").strip())
    return _client

MODEL = "gpt-4o-mini"


async def _chat(system: str, user: str) -> str:
    """Thin wrapper: sends a chat completion and returns the content string."""
    response = await _get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()


# ── Segment builder ───────────────────────────────────────────────────────────

SEGMENT_SYSTEM = """You are a CRM segment builder. Convert natural language descriptions \
into segment rules JSON.

Available fields: total_spent (float), purchase_count (int), \
last_purchase_date (datetime), city (string), age (int), gender (string), tags (array).

Available ops: eq, neq, gte, lte, gt, lt, in, not_in, days_ago_lte, days_ago_gte, contains.
Operator is AND or OR.

Return ONLY valid JSON in this exact format:
{"operator": "AND", "conditions": [{"field": "...", "op": "...", "value": ...}]}
No explanation, no markdown, no backticks. Pure JSON only."""


async def build_segment_from_prompt(prompt: str) -> dict:
    """
    Convert a plain-English segment description into a rules dict.
    Falls back to an empty AND rules dict on JSON parse failure.
    """
    try:
        raw = await _chat(SEGMENT_SYSTEM, prompt)
        # Strip accidental backtick wrapping from the model
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"[AI] build_segment_from_prompt parse error: {e}")
        return {"operator": "AND", "conditions": []}


# ── Message variants ──────────────────────────────────────────────────────────

MESSAGE_SYSTEM = "You are a marketing copywriter for consumer brands."


async def write_message_variants(
    brand: str,
    segment_desc: str,
    channel: str,
    goal: str,
) -> list[dict]:
    """
    Generate 3 message variants (friendly / urgent / value-focused).
    SMS capped at 160 chars; WhatsApp/Email at 1000 chars.
    """
    user_prompt = (
        f"Write 3 message variants for {brand} targeting {segment_desc} "
        f"via {channel}. Goal: {goal}. Tones: friendly, urgent, value-focused. "
        f"SMS max 160 chars. WhatsApp/Email max 1000 chars. "
        f'Return ONLY JSON array: [{{"tone": "...", "message": "..."}}]. No explanation.'
    )
    try:
        raw = await _chat(MESSAGE_SYSTEM, user_prompt)
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"[AI] write_message_variants parse error: {e}")
        # Safe fallback — one placeholder variant
        return [{"tone": "friendly", "message": f"Hi! Exciting news from {brand}. {goal}"}]


# ── Campaign insights ─────────────────────────────────────────────────────────

INSIGHTS_SYSTEM = "You are a senior CRM analyst. Provide concise, actionable insights."


async def get_campaign_insights(
    stats: dict,
    segment_rules: dict,
    channel: str,
) -> list[dict]:
    """
    Return exactly 3 insights + 2 recommendations for a campaign.
    """
    user_prompt = (
        f"Campaign performance: {json.dumps(stats)}. "
        f"Segment rules: {json.dumps(segment_rules)}. "
        f"Channel: {channel}. "
        f"Give exactly 3 insights and 2 recommendations. "
        f'Return ONLY JSON array: [{{"type": "insight"|"recommendation", "text": "..."}}]'
    )
    try:
        raw = await _chat(INSIGHTS_SYSTEM, user_prompt)
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"[AI] get_campaign_insights parse error: {e}")
        return [
            {"type": "insight", "text": "Unable to generate insights at this time."},
            {"type": "recommendation", "text": "Review campaign delivery logs manually."},
        ]


# ── One-shot campaign creator ─────────────────────────────────────────────────

async def create_campaign_from_intent(intent: str) -> dict:
    """
    Orchestrates 2 AI calls to go from intent → rules + message variants.
    The route handler saves results to DB and returns a full campaign object.

    Step 1: Build segment rules from the intent string.
    Step 2: Write 3 message variants based on the same intent.
    Step 3: Return combined dict for the route to persist.
    """
    # Step 1 — segment rules
    rules = await build_segment_from_prompt(intent)

    # Step 2 — message variants
    # Extract a short segment description from the intent for the message prompt
    segment_desc = intent[:200]  # keep it brief for the copywriter
    variants = await write_message_variants(
        brand="BrewCo",
        segment_desc=segment_desc,
        channel="whatsapp",  # default; overridden in DB by campaign.channel
        goal=intent,
    )

    return {
        "rules": rules,
        "message_variants": variants,
        "parsed_intent": intent,
    }
