# BrewCo CRM — AI-Native Mini CRM

> An AI-powered CRM for BrewCo coffee chain to segment shoppers, craft personalised messages, run campaigns, and track delivery performance.

📖 **How it all fits together** (architecture, data flow, every feature step by step): see [flow.md](flow.md).

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  BrewCo CRM Frontend                │
│              (React + Vite, port 5173)              │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP
┌─────────────────────▼───────────────────────────────┐
│              CRM Backend (FastAPI :8000)             │
│  /api/customers  /api/segments  /api/campaigns       │
│  /api/analytics  /api/ai  /api/receipts              │
└──────┬──────────────────────────────┬───────────────┘
       │ PostgreSQL                   │ HTTP /send
       ▼                             ▼
┌─────────────┐           ┌──────────────────────┐
│  PostgreSQL │           │  Channel Service      │
│  (brewco)   │           │  (FastAPI :8001)      │
└─────────────┘           │  Simulates delivery   │
                          │  async callbacks ──►  │
                          │  POST /api/receipts/  │
                          │  callback             │
                          └──────────────────────┘
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL (local install)
- Node.js 18+ (for frontend, built separately)

### Step 1 — Create the PostgreSQL database
```bash
psql -U postgres -c "CREATE DATABASE brewco;"
```

### Step 2 — Setup CRM Service
```bash
cd crm-service
pip install -r requirements.txt
cp .env.example .env       # fill in your DATABASE_URL and OPENAI_API_KEY
alembic upgrade head       # run migrations
python seed.py             # seed sample customers + orders (skips if already seeded)
uvicorn app.main:app --port 8000 --reload
```

### Step 3 — Setup Channel Service (new terminal)
```bash
cd channel-service
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --port 8001 --reload
```

### Step 4 — Verify
Open **http://localhost:8000/docs** to explore the API via Swagger UI.

---

## Deploy to Render (Production)

This project includes a `render.yaml` Blueprint for **one-click deployment**.

### Option A — Blueprint (Recommended)
1. Push this repo to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com/) → **New** → **Blueprint**
3. Connect your GitHub repo and select the `main` branch
4. Render auto-detects `render.yaml` and creates (all in the Singapore region):
   - **brewco-crm-app** — CRM backend + React frontend (Python web service)
   - **brewco-channel-app** — Channel simulation service (Python web service)
   - **brewco-postgres** — PostgreSQL database (free tier)
5. When asked, enter `OPENAI_API_KEY` and `APP_PASSWORD` (the password the site will ask for)
6. Deploy! The build script handles: pip install → npm build → migrations → seed
7. Open the `brewco-crm-app` URL and sign in with username `admin` and your `APP_PASSWORD`

### Option B — Manual Setup
1. Create a PostgreSQL database on Render
2. Create two Web Services pointing to `crm-service/` and `channel-service/`
3. Set environment variables (see below)
4. Build command: `chmod +x build.sh && ./build.sh`
5. Start command: `gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`

---

## Environment Variables

### crm-service/.env

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL async connection string | `postgresql+asyncpg://postgres:password@localhost:5432/brewco` |
| `OPENAI_API_KEY` | OpenAI API key for gpt-4o-mini calls | *(required)* |
| `CHANNEL_SERVICE_URL` | Base URL of the channel service | `http://localhost:8001` |
| `APP_PASSWORD` | Password-protects the whole site (browser login box). Empty = no password | *(empty)* |
| `APP_USERNAME` | Username for the login box | `admin` |
| `CALLBACK_SECRET` | Shared secret with the channel service. Empty = not checked | *(empty)* |

### channel-service/.env

| Variable | Description | Default |
|---|---|---|
| `CRM_CALLBACK_URL` | CRM service URL for receipt callbacks | `http://localhost:8000` |
| `CALLBACK_SECRET` | Must match the CRM's `CALLBACK_SECRET` | *(empty)* |

---

## API Reference

### Customers
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/customers` | Paginated list with filters (city, min/max spent, search) |
| `POST` | `/api/customers` | Create single customer |
| `POST` | `/api/customers/bulk` | Bulk insert customers |
| `GET` | `/api/customers/{id}` | Customer detail + last 10 orders |

### Segments
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/segments` | List all segments |
| `POST` | `/api/segments` | Create segment (auto-computes customer count) |
| `POST` | `/api/segments/preview` | Preview rules without saving |
| `GET` | `/api/segments/{id}/customers` | Paginated customers matching segment |
| `DELETE` | `/api/segments/{id}` | Delete segment |

### Campaigns
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/campaigns` | List all campaigns |
| `POST` | `/api/campaigns` | Create draft campaign |
| `POST` | `/api/campaigns/{id}/launch` | Launch campaign (async background) |
| `GET` | `/api/campaigns/{id}` | Campaign detail |
| `GET` | `/api/campaigns/{id}/stats` | Delivery funnel stats with rates |

### Receipts
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/receipts/callback` | Inbound delivery receipt from channel service |

### Analytics
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/analytics/overview` | Dashboard KPIs (total customers, avg delivery rate, top channel) |
| `GET` | `/api/analytics/campaigns` | All campaigns with full funnel stats |

### AI
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/ai/build-segment` | NL prompt → segment rules JSON + preview |
| `POST` | `/api/ai/write-message` | Generate 3 message variants (friendly/urgent/value) |
| `GET` | `/api/ai/insights/{campaign_id}` | 3 insights + 2 recommendations for a campaign |
| `POST` | `/api/ai/create-campaign` | One-shot: intent → segment + campaign + messages |

### System
| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | CRM service health check |
| `GET` | `http://localhost:8001/health` | Channel service health check |

---

## Design Decisions

### Two-service architecture
Mirrors how real async delivery providers (Twilio, MSG91, Kaleyra) work. The CRM fires a batch send request and gets notified via webhooks — it doesn't maintain an open connection waiting for delivery. This decoupling means the channel service can be swapped for a real provider with zero CRM code changes.

### PostgreSQL JSON for segment rules
Rules are stored as `{ "operator": "AND", "conditions": [...] }` in a JSON column rather than a normalised EAV table. Benefits:
- Rules schema evolves without migrations
- The RulesEngine reads the same dict shape that the API receives
- PostgreSQL JSONB enables indexing on specific paths later

### Async FastAPI throughout
Campaign launches involve N HTTP calls to the channel service (N = customer count). Running these synchronously would block the event loop and time out for large segments. Async keeps the server responsive for other requests during launches.

### BackgroundTasks for campaign launch
`POST /api/campaigns/{id}/launch` returns a 200 instantly. The actual send loop runs in a `BackgroundTask` with its **own** database session (not the request session, which closes when the response is sent). This is the canonical pattern for long-running work in async FastAPI.

### Password protection instead of user accounts
A single shared password (HTTP Basic auth, `APP_PASSWORD`) keeps a deployed instance private without building a login system; the two services authenticate to each other with `CALLBACK_SECRET`. Both are off when unset, so local dev needs no setup. See `app/security.py` and the "Password protection" section of [flow.md](flow.md). For real multi-user use: JWT (via `python-jose`) with role-based access (marketing manager vs. read-only analyst).

### No Redis / Celery
The in-memory `pending_callbacks` list in the channel service is sufficient at demo scale. The 30-second retry worker covers transient failures.

---

## Tradeoffs & Scale

At **10× scale** (2,000 customers, 50 campaigns/day):

| Concern | Fix |
|---|---|
| `BackgroundTasks` exhaustion | Replace with **Celery + Redis** worker queue; each campaign launch becomes a Celery task |
| Segment query performance | Add **DB indices** on `Customer`: `city`, `total_spent`, `last_purchase_date`, `purchase_count` |
| Callback lookup speed | Add index on `Communication.external_id` (already unique, Postgres auto-indexes unique constraints) |
| Callback reliability | Replace in-memory list with **SQS / Kafka** topic for guaranteed at-least-once delivery |
| Receipt endpoint abuse | Add **rate limiting** on `/api/receipts/callback` (e.g., `slowapi`) |
| Segment preview latency | **Cache** preview counts in Redis with 5-minute TTL |
| AI latency | Add **async queue** for AI requests; return job ID immediately, poll for result |

---

## Project Structure

```
xeno-mini-crm/
├── crm-service/
│   ├── app/
│   │   ├── main.py                    # FastAPI app + router mounts
│   │   ├── security.py                # optional site password + service secret
│   │   ├── api/routes/
│   │   │   ├── customers.py           # CRUD + bulk + detail
│   │   │   ├── campaigns.py           # Draft/launch/stats
│   │   │   ├── segments.py            # Rules-based segments
│   │   │   ├── receipts.py            # Delivery receipt webhook
│   │   │   ├── analytics.py           # Dashboard KPIs
│   │   │   └── ai.py                  # OpenAI-powered endpoints
│   │   ├── models/                    # SQLAlchemy ORM models
│   │   ├── schemas/                   # Pydantic v2 schemas
│   │   ├── services/
│   │   │   ├── segmentation.py        # RulesEngine (dynamic SQL builder)
│   │   │   ├── ai_service.py          # gpt-4o-mini wrappers
│   │   │   ├── channel_client.py      # httpx batch sender w/ retry
│   │   │   └── campaign_service.py    # Launch orchestrator
│   │   └── db/
│   │       ├── database.py            # Async engine + session
│   │       └── seed.py                # 200 customers + 600 orders
│   ├── alembic/                       # Async migration config
│   ├── frontend/                      # React app (build separately)
│   ├── requirements.txt
│   └── .env.example
├── channel-service/
│   ├── app/
│   │   ├── main.py                    # /send endpoint + startup worker
│   │   ├── simulator.py               # Async delivery simulation
│   │   └── callback_worker.py         # 30s retry loop
│   ├── requirements.txt
│   └── .env.example
├── render.yaml                        # Render Blueprint (2 services + Postgres)
├── flow.md                            # how everything works, with diagrams
└── README.md
```
