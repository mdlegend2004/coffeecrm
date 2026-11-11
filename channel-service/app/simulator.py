"""
channel-service/app/simulator.py — Async delivery simulation.

Simulates real-world channel delivery behaviour:
  - 85% messages delivered, 15% failed
  - 60% of delivered messages get opened
  - 35% of opened messages get clicked

Each step has a random delay to mimic network latency.
Callbacks are posted to the CRM /api/receipts/callback endpoint.
Failed callbacks are queued in pending_callbacks for retry.
"""

from __future__ import annotations
import asyncio
import random
from datetime import datetime, timezone

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

# Shared secret the CRM checks on every callback (empty = CRM accepts any callback)
CALLBACK_SECRET = os.getenv("CALLBACK_SECRET", "")
AUTH_HEADERS = {"X-Callback-Secret": CALLBACK_SECRET}


async def send_callback(
    client: httpx.AsyncClient,
    crm_url: str,
    external_id: str,
    status: str,
    pending_callbacks: list,
) -> bool:
    """POST a single delivery receipt to the CRM callback endpoint."""
    payload = {
        "external_id": external_id,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    for attempt in range(3):
        try:
            response = await client.post(
                f"{crm_url}/api/receipts/callback",
                json=payload,
                headers=AUTH_HEADERS,
                timeout=10.0,
            )
            if response.status_code == 200:
                print(f"[CALLBACK] {external_id} -> {status} OK")
                return True
        except Exception as e:
            print(f"[CALLBACK FAILED] {external_id} -> {status} attempt {attempt + 1}: {e}")
            await asyncio.sleep(1)

    # All attempts exhausted — queue for retry
    pending_callbacks.append(payload)
    return False


async def simulate_delivery(item: dict, crm_url: str, pending_callbacks: list) -> None:
    """
    Full delivery simulation pipeline for a single message:
      1. Random network delay (1–4s)
      2. 85% delivered / 15% failed
      3. If delivered: 60% chance open (after 3–8s delay)
      4. If opened: 35% chance click (after 2–6s delay)
    """
    external_id = item["external_id"]

    async with httpx.AsyncClient() as client:
        # Simulate initial network transit
        await asyncio.sleep(random.uniform(1, 4))

        # Delivery outcome
        if random.random() < 0.85:
            outcome = "delivered"
        else:
            outcome = "failed"

        await send_callback(client, crm_url, external_id, outcome, pending_callbacks)

        if outcome != "delivered":
            return

        # Simulate open (60% chance)
        await asyncio.sleep(random.uniform(3, 8))
        if random.random() < 0.60:
            await send_callback(client, crm_url, external_id, "opened", pending_callbacks)

            # Simulate click (35% chance if opened)
            await asyncio.sleep(random.uniform(2, 6))
            if random.random() < 0.35:
                await send_callback(client, crm_url, external_id, "clicked", pending_callbacks)
