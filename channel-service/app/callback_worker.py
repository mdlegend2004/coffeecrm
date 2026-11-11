"""
channel-service/app/callback_worker.py — Background retry worker.

Polls pending_callbacks every 30 seconds and retries any callbacks
that failed during the initial delivery simulation.

This mirrors how real message brokers (SQS, Kafka) provide at-least-once
delivery guarantees. For this demo scale, an in-memory list is sufficient.
"""

from __future__ import annotations
import asyncio

import httpx

from app.simulator import AUTH_HEADERS


async def retry_pending_callbacks(pending_callbacks: list, crm_url: str) -> None:
    """
    Long-running coroutine: retries failed callbacks every 30 seconds.
    Started as an asyncio task in main.py's startup event.
    """
    while True:
        await asyncio.sleep(30)

        if not pending_callbacks:
            continue

        print(f"[RETRY WORKER] Retrying {len(pending_callbacks)} pending callbacks")

        # Snapshot and clear the list — any new failures during retry go back in
        retry_list = pending_callbacks.copy()
        pending_callbacks.clear()

        async with httpx.AsyncClient() as client:
            for payload in retry_list:
                try:
                    response = await client.post(
                        f"{crm_url}/api/receipts/callback",
                        json=payload,
                        headers=AUTH_HEADERS,
                        timeout=10.0,
                    )
                    if response.status_code != 200:
                        # CRM returned non-200, requeue
                        pending_callbacks.append(payload)
                    else:
                        print(f"[RETRY WORKER] OK {payload.get('external_id')}")
                except Exception as e:
                    print(f"[RETRY WORKER] FAIL {payload.get('external_id')}: {e}")
                    pending_callbacks.append(payload)
