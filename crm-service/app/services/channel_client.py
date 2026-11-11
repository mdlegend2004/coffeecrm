"""
services/channel_client.py — Async HTTP client for the channel service.

Design:
  - Uses httpx.AsyncClient (not requests) so we don't block the event loop.
  - 3-attempt retry with exponential backoff: 1s → 2s → 4s.
    This handles transient network blips without hammering the channel service.
  - Returns a result dict keyed by external_id so the caller can map
    each message to its outcome without re-querying the DB.
  - On total failure after 3 attempts, returns "failed" for that external_id.
    The campaign_service then marks the Communication as failed.
"""

from __future__ import annotations
import asyncio
import logging
import os
from typing import Dict, List

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

def _normalise_url(url: str) -> str:
    """Accept 'host', 'host/' or 'https://host/' and return 'https://host' (http kept for localhost)."""
    url = url.strip().rstrip("/")
    if url and "://" not in url:
        url = ("http://" if url.startswith(("localhost", "127.0.0.1")) else "https://") + url
    return url


CHANNEL_SERVICE_URL = _normalise_url(os.getenv("CHANNEL_SERVICE_URL", "http://localhost:8001"))
# Shared secret proving to the channel service that this request came from the CRM
CALLBACK_SECRET = os.getenv("CALLBACK_SECRET", "")

# Exponential backoff delays in seconds
RETRY_DELAYS = [1, 2, 4]


async def send_batch(communications: List[dict]) -> Dict[str, str]:
    """
    POST a batch of messages to the channel service.

    Each item in communications:
      { "external_id": str, "recipient": str, "channel": str, "message": str }

    Returns:
      { external_id: "accepted" | "failed" }
    """
    result: Dict[str, str] = {}

    # Initialise all as failed — overwrite on success
    for item in communications:
        result[item["external_id"]] = "failed"

    for attempt, delay in enumerate(RETRY_DELAYS):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{CHANNEL_SERVICE_URL}/send",
                    json=communications,
                    headers={"X-Callback-Secret": CALLBACK_SECRET},
                )
                if response.status_code == 200:
                    # Mark all as accepted on batch success
                    for item in communications:
                        result[item["external_id"]] = "accepted"
                        logger.info(f"[CHANNEL] accepted ext_id={item['external_id']}")
                    return result
                else:
                    logger.warning(
                        f"[CHANNEL] attempt {attempt + 1} → HTTP {response.status_code}"
                    )
        except httpx.RequestError as e:
            logger.warning(f"[CHANNEL] attempt {attempt + 1} failed: {e}")

        if attempt < len(RETRY_DELAYS) - 1:
            await asyncio.sleep(delay)

    # All 3 attempts failed
    logger.error(f"[CHANNEL] batch failed after {len(RETRY_DELAYS)} attempts")
    return result
