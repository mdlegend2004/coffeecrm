"""
crm-service/app/main.py — FastAPI application entry point.

Design:
  - CORS is wide-open ("*") for local dev. In production, restrict
    allow_origins to your actual frontend domain.
  - StaticFiles serves the built React app from frontend/dist/ in
    production. The mount is guarded by os.path.exists() so it
    doesn't crash in dev when the dist folder hasn't been built yet.
  - All routers share a consistent /api/* prefix for easy nginx proxying.
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import customers, campaigns, segments, receipts, analytics, ai
from app.security import access_guard

app = FastAPI(
    title="BrewCo CRM API",
    version="1.0.0",
    description="AI-native Mini CRM for BrewCo coffee chain",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Password protection — active only when APP_PASSWORD / CALLBACK_SECRET are set
# (see app/security.py). Local dev without them is unaffected.
app.middleware("http")(access_guard)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(customers.router, prefix="/api/customers", tags=["customers"])
app.include_router(segments.router,  prefix="/api/segments",  tags=["segments"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
app.include_router(receipts.router,  prefix="/api/receipts",  tags=["receipts"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(ai.router,        prefix="/api/ai",         tags=["ai"])


@app.get("/health", tags=["system"])
async def health():
    """Liveness check: returns 200 so you (or Render) can tell the CRM API is up."""
    return {"status": "ok", "service": "crm"}


# ── Frontend — serve built React app in production ────────────────────────────
# The dist/ folder only exists after `cd frontend && npm run build`.
# In dev (no dist/), this block is skipped and Vite handles the frontend.
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
