# How BrewCo CRM Works

This document explains how the pieces of the project fit together: what runs where, what talks to what, and what happens step by step when you use each feature. For setup commands and the full API table, see [README.md](README.md).

---

## 1. The big picture

The system is **three running programs, one database, and one outside service**:

```mermaid
flowchart LR
    U([You, in the browser]) --> FE

    subgraph CRM_BOX [crm-service]
        FE["React frontend<br/>Vite dev server :5173<br/>(or frontend/dist served by FastAPI in prod)"]
        API["CRM API<br/>FastAPI :8000"]
    end

    FE -- "/api/* (HTTP, via Vite proxy)" --> API
    API -- "SQL (asyncpg)" --> DB[(PostgreSQL<br/>database: brewco)]
    API -- "chat completions" --> OAI[[OpenAI<br/>gpt-4o-mini]]
    API -- "POST /send (batches of 50)" --> CH["Channel service<br/>FastAPI :8001"]
    CH -- "POST /api/receipts/callback<br/>(delivered / failed / opened / clicked)" --> API
```

| Piece | Folder | Port | Job |
|---|---|---|---|
| Frontend | `crm-service/frontend/` | 5173 | The screens you click. Talks **only** to the CRM API. |
| CRM API | `crm-service/app/` | 8000 | All business logic. The only thing that touches the database or OpenAI. |
| Channel service | `channel-service/app/` | 8001 | Pretends to be an SMS / WhatsApp / email provider. Sends delivery updates back to the CRM. |
| PostgreSQL | (local install / Render DB) | 5432 | Stores customers, orders, segments, campaigns and messages. |
| OpenAI | external | — | Writes segment rules, message copy and campaign insights. |

The frontend never talks to the channel service, the database, or OpenAI directly. Everything goes through the CRM API.

---

## 2. Running it locally

Start three terminals (all from `xeno-mini-crm/`), plus a running PostgreSQL:

```bash
# 1) CRM API
cd crm-service
alembic upgrade head            # create / update tables
python seed.py                  # sample data (skips if customers already exist)
uvicorn app.main:app --port 8000

# 2) Channel service
cd channel-service
uvicorn app.main:app --port 8001

# 3) Frontend
cd crm-service/frontend
npm install
npm run dev                     # http://localhost:5173
```

> **Note:** On this machine, `uvicorn --reload` doesn't notice file changes on the `E:` drive. After editing Python code, stop the server (Ctrl+C) and start it again.

API docs (Swagger) are at http://localhost:8000/docs.

---

## 3. What is connected to what

### Frontend → API → backend code

Every screen calls a function in [`frontend/src/api.js`](crm-service/frontend/src/api.js). Each of those calls one API endpoint, which is handled by a route file and usually a service.

| Screen (`frontend/src/pages/`) | `api.js` functions it calls | Endpoint | Route file → service |
|---|---|---|---|
| **Dashboard** | `getOverview`, `getAnalyticsCampaigns` | `GET /api/analytics/overview`, `GET /api/analytics/campaigns` | `routes/analytics.py` |
| **Customers** | `getCustomers`, `getCustomer` | `GET /api/customers/`, `GET /api/customers/{id}` | `routes/customers.py` |
| **Segments** (list, delete) | `getSegments`, `deleteSegment` | `GET /api/segments/`, `DELETE /api/segments/{id}` | `routes/segments.py` |
| **Segments → Manual rules** | `previewSegment`, `createSegment` | `POST /api/segments/preview`, `POST /api/segments/` | `routes/segments.py` → `services/segmentation.py` |
| **Segments → Build with AI** | `aiBuildSegment`, `createSegment` | `POST /api/ai/build-segment` | `routes/ai.py` → `services/ai_service.py` + `segmentation.py` |
| **Campaigns** (list, launch) | `getAnalyticsCampaigns`, `launchCampaign` | `GET /api/analytics/campaigns`, `POST /api/campaigns/{id}/launch` | `routes/campaigns.py` → `services/campaign_service.py` |
| **Campaigns → New campaign wizard** | `getSegments`, `aiWriteMessage`, `createCampaign`, `launchCampaign` | `POST /api/ai/write-message`, `POST /api/campaigns/` | `routes/ai.py`, `routes/campaigns.py` |
| **Campaign detail** | `getCampaignStats` (every 4 s), `aiInsights` | `GET /api/campaigns/{id}/stats`, `GET /api/ai/insights/{id}` | `routes/campaigns.py`, `routes/ai.py` |
| **AI Assistant** | `aiCreateCampaign`, `launchCampaign` | `POST /api/ai/create-campaign` | `routes/ai.py` → `ai_service.py` |

Shared UI helpers live in `frontend/src/components/` (`ui.jsx`: badges, spinner, ₹/%/"3d ago" formatters; `useCountUp.js`: the dashboard's counting animation). `main.jsx` mounts the app and draws the floating coffee-bean background; `App.jsx` holds the sidebar and maps URLs to pages.

### Inside the CRM API

```mermaid
flowchart TD
    main["app/main.py<br/>creates the FastAPI app, mounts routers,<br/>serves frontend/dist in production"]
    main --> R

    subgraph R [app/api/routes/ — HTTP endpoints]
        rc[customers.py]
        rs[segments.py]
        rca[campaigns.py]
        rr[receipts.py]
        ran[analytics.py]
        rai[ai.py]
    end

    subgraph S [app/services/ — logic]
        seg["segmentation.py<br/>RulesEngine: rules JSON → SQL"]
        camp["campaign_service.py<br/>launch_campaign()"]
        chc["channel_client.py<br/>send_batch() with retries"]
        ais["ai_service.py<br/>OpenAI prompts + safe fallbacks"]
    end

    rs --> seg
    rai --> seg
    rai --> ais
    rca --> camp
    camp --> seg
    camp --> chc
    chc -->|HTTP| CH[(channel service)]
    ais -->|HTTP| OAI[(OpenAI)]

    R --> M["app/models/ — database tables (SQLAlchemy)"]
    R --> SC["app/schemas/ — request/response shapes (Pydantic)"]
    M --> DBP["app/db/database.py<br/>engine + get_db() session per request"]
```

- **models/** define the tables. **schemas/** define the JSON that goes in and out of the API, and validate it. Routes convert between the two.
- **`app/models/__init__.py`** imports every model. SQLAlchemy needs all of them loaded to resolve relationships like `Customer.orders`, so this lets any script import a single model safely.
- **`db/database.py`** reads `DATABASE_URL` from `.env`. `get_db()` gives each request its own database session and closes it afterwards.

---

## 4. The data model

```mermaid
erDiagram
    CUSTOMER ||--o{ ORDER : places
    CUSTOMER ||--o{ COMMUNICATION : receives
    SEGMENT  |o--o{ CAMPAIGN : "targets (nullable)"
    CAMPAIGN ||--o{ COMMUNICATION : sends

    CUSTOMER {
        uuid id
        string name
        string email "unique"
        string city
        float total_spent "sum of completed orders"
        int purchase_count "number of completed orders"
        datetime last_purchase_date
        string[] tags "vip, loyal, at-risk..."
    }
    ORDER {
        uuid id
        float amount
        string status "completed / pending / returned"
    }
    SEGMENT {
        uuid id
        string name
        json rules "operator + conditions"
        int customer_count "cached when saved"
        bool ai_generated
    }
    CAMPAIGN {
        uuid id
        string channel "whatsapp / sms / email / rcs"
        string message_template "may contain {name}"
        string status "draft / running / completed / failed"
    }
    COMMUNICATION {
        uuid id
        string external_id "shared with channel service"
        string message "personalised text"
        string status "queued → ... → converted / failed"
        datetime sent_at
        datetime delivered_at
    }
```

A **segment doesn't store a list of customers**. It stores *rules*, and the matching customers are worked out fresh each time they're needed. `customer_count` is only a snapshot taken when the segment was saved.

---

## 5. Feature flows, step by step

### 5.1 Segments: from rules to a list of customers

A segment's rules look like this:

```json
{ "operator": "AND",
  "conditions": [
    { "field": "city",        "op": "eq",  "value": "Mumbai" },
    { "field": "total_spent", "op": "gte", "value": 2000 } ] }
```

`RulesEngine` in [`services/segmentation.py`](crm-service/app/services/segmentation.py) turns each condition into a SQL filter and joins them with AND/OR:

- **Fields:** `total_spent`, `purchase_count`, `last_purchase_date`, `city`, `age`, `gender`, `tags`
- **Ops:** `eq neq gt gte lt lte in not_in` (normal comparisons), `days_ago_lte N` ("bought within the last N days"), `days_ago_gte N` ("hasn't bought for N+ days"), `contains` (customer has this tag)
- `city` and `gender` match case-insensitively. Numbers sent as text are converted. Unknown fields are skipped.

It offers `count()`, `get_ids()` and `sample(n)`. These are used by preview, save, the AI builder and campaign launch.

**Manual builder:** form rows → `buildRules()` in the browser → `POST /api/segments/preview` (count + 5 examples, nothing saved) → `POST /api/segments/` (saved, with `customer_count` computed).

**AI builder:** your sentence → `POST /api/ai/build-segment` → `ai_service.build_segment_from_prompt()` asks OpenAI to reply with rules JSON only → the CRM runs the rules through `RulesEngine` for a live count → you check it and save. If OpenAI returns something unreadable, you get empty rules instead of an error.

### 5.2 Launching a campaign (the main flow)

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant API as CRM API (:8000)
    participant DB as PostgreSQL
    participant CH as Channel service (:8001)

    B->>API: POST /api/campaigns/{id}/launch
    API->>DB: campaign must be "draft" → set "running"
    API-->>B: 200 "Campaign launched" (returns immediately)

    Note over API: background task launch_campaign()
    API->>DB: load segment rules → RulesEngine.get_ids()
    API->>DB: insert one Communication per customer<br/>(status queued, {name} replaced, new external_id)
    loop every 50 messages
        API->>CH: POST /send [ {external_id, recipient, channel, message}, ... ]
        CH-->>API: {"accepted": 50}
        API->>DB: mark those rows "sent"
    end
    API->>DB: campaign → "completed"

    Note over CH: per message, simulate_delivery()
    CH->>API: POST /api/receipts/callback {external_id, "delivered" (85%) or "failed"}
    CH->>API: ...later "opened" (60% of delivered)
    CH->>API: ...later "clicked" (35% of opened)
    API->>DB: update that Communication's status<br/>(15% of clicks become "converted")

    loop every 4 seconds
        B->>API: GET /api/campaigns/{id}/stats
        API-->>B: funnel counts + rates
    end
```

Key points:

1. **The launch request returns straight away.** The sending runs in a background task (`asyncio.create_task`) with its **own** database session, because the request's session closes when the response is sent.
2. **No double sends.** The endpoint switches the campaign to `running` *before* starting the task, so a second click gets `400 "already running"`.
3. **Who gets it:** the segment's rules are evaluated *at launch time*, so new customers who now match are included. If the segment was deleted (`segment_id` is NULL) or matches nobody, the campaign is marked `failed`.
4. **`external_id`** is a random UUID stored on each Communication and sent to the channel service. The channel service passes it back in every callback, which is how the CRM knows which row to update.
5. **Retries, CRM → channel:** `channel_client.send_batch()` tries each batch 3 times (waiting 1 s, then 2 s). If all tries fail, those messages are marked `failed`.
6. **Retries, channel → CRM:** each callback is tried 3 times. If it still fails, it goes into an in-memory `pending_callbacks` list, which `callback_worker.py` retries every 30 s. (Restarting the channel service empties this list.)
7. **Status only moves forward.** `routes/receipts.py` ignores a callback that would move a message *back* (e.g. a late `delivered` arriving after `clicked`). Unknown `external_id`s are accepted and ignored, so retries are always safe.

### 5.3 How the numbers are calculated

The message statuses form a funnel. A message that reached a later stage also counts for every earlier one:

```mermaid
stateDiagram-v2
    [*] --> queued
    queued --> sent : channel accepted the batch
    queued --> failed : channel unreachable after retries
    sent --> delivered : 85%
    sent --> failed : 15%
    delivered --> opened : 60%
    opened --> clicked : 35%
    clicked --> converted : 15% (random, in the CRM)
```

| Number | Counts messages with status in |
|---|---|
| sent | sent, delivered, opened, read, clicked, converted |
| delivered | delivered, opened, read, clicked, converted |
| opened | opened, read, clicked, converted |
| clicked | clicked, converted |
| failed | failed |

| Rate | Formula |
|---|---|
| Delivery rate | delivered ÷ (sent + failed) |
| Open rate | opened ÷ delivered |
| Click rate | clicked ÷ opened |
| Conversion rate | converted ÷ clicked |

This same logic is used in three places that must stay in sync: `routes/campaigns.py` (`/stats`), `routes/analytics.py` (dashboard and campaign list), and `routes/ai.py` (the numbers sent to the AI for insights). The dashboard's *Avg delivery rate* is the average of the delivery rates of **completed** campaigns.

### 5.4 The AI features

All four live in [`services/ai_service.py`](crm-service/app/services/ai_service.py) and use `gpt-4o-mini` with the key from `OPENAI_API_KEY`. Each one asks for JSON only and has a safe fallback, so a bad AI reply never crashes the API.

| Feature | Endpoint | Used by | What it does |
|---|---|---|---|
| Build segment | `POST /api/ai/build-segment` | Segments → Build with AI | English → rules JSON, then a live match count and sample |
| Write message | `POST /api/ai/write-message` | New campaign wizard → Write with AI | 3 variants: friendly, urgent, value-focused (SMS ≤ 160 chars) |
| Insights | `GET /api/ai/insights/{id}` | Campaign detail → Generate | Sends the funnel stats and segment rules; gets back 3 insights + 2 recommendations |
| One-shot campaign | `POST /api/ai/create-campaign` | AI Assistant | Build segment + write messages → **saves** a segment and a **draft** WhatsApp campaign using the first variant. You still press Launch. |

### 5.5 Customers

- **List:** `GET /api/customers/` with `page`, `limit`, `city` (exact match), `min_spent`, `max_spent`, `search` (name or email, case-insensitive). Returns `{items, total, page, limit}`.
- **Detail:** `GET /api/customers/{id}` adds the 10 most recent orders.
- **Create:** `POST /api/customers/` and `POST /api/customers/bulk`. A duplicate email returns **409**, and bulk inserts are all-or-nothing.
- `total_spent` and `purchase_count` count **completed** orders only. A customer can therefore show ₹0 / 0 orders and still have a *returned* order in their history.

---

## 6. Configuration

| File | Variable | Used by | Default |
|---|---|---|---|
| `crm-service/.env` | `DATABASE_URL` | `db/database.py`, Alembic | `postgresql+asyncpg://postgres:password@localhost:5432/brewco` (`postgres://` URLs from Render are converted automatically) |
| | `OPENAI_API_KEY` | `services/ai_service.py` | *(required for AI features)* |
| | `CHANNEL_SERVICE_URL` | `services/channel_client.py` | `http://localhost:8001` |
| | `APP_PASSWORD` | `app/security.py` | empty → **no password** (local dev). Set it to password-protect the whole site. |
| | `APP_USERNAME` | `app/security.py` | `admin` |
| | `CALLBACK_SECRET` | `app/security.py`, `services/channel_client.py` | empty → not checked. Must match the channel service's value. |
| `channel-service/.env` | `CRM_CALLBACK_URL` | `channel-service/app/main.py` | `http://localhost:8000` |
| | `CALLBACK_SECRET` | `app/simulator.py`, `app/main.py` | empty → not checked. Must match the CRM's value. |
| frontend (build time) | `VITE_API_URL` | `frontend/src/api.js` | empty → same origin (`/api` is proxied to :8000 by `vite.config.js`) |

---

## 7. Deployment (Render)

[`render.yaml`](render.yaml) creates three resources, all in the **Singapore** region. They must share a region, because the database's internal address only works within one region:

- **brewco-postgres**: PostgreSQL (free plan, which Render expires after a while; see below).
- **brewco-crm-app**: runs [`crm-service/build.sh`](crm-service/build.sh) (pip install → `npm run build` → `alembic upgrade head` → `python seed.py`), then gunicorn with 2 workers. In production there's no Vite server: `app/main.py` serves `frontend/dist/` itself, so the frontend and API share one URL.
- **brewco-channel-app**: runs gunicorn with **1 worker**. It has to stay at 1, because `pending_callbacks` lives in memory and isn't shared between workers.

The two services find each other through `RENDER_EXTERNAL_URL`. `OPENAI_API_KEY` and `APP_PASSWORD` must be set by hand in the dashboard.

### Password protection

The site is private by password. There's no login page or user accounts; [`app/security.py`](crm-service/app/security.py) is a small middleware that checks every request:

```mermaid
flowchart TD
    R[Incoming request to the CRM] --> H{path?}
    H -- "/health" --> OK[allowed]
    H -- "/api/receipts/callback" --> S{"X-Callback-Secret header<br/>matches CALLBACK_SECRET?"}
    S -- yes --> OK
    S -- no --> F[403]
    H -- "anything else<br/>(pages, /api/*, /docs)" --> P{"browser sent<br/>admin + APP_PASSWORD?"}
    P -- yes --> OK
    P -- no --> A["401 → browser shows its<br/>username/password box"]
```

- **You:** open the site, type `admin` and your `APP_PASSWORD` once, and the browser remembers it for the session. The frontend's API calls go to the same address, so they reuse it automatically.
- **CRM → channel service:** `channel_client.send_batch()` sends `X-Callback-Secret`, and the channel service's `/send` rejects requests without it (403).
- **Channel service → CRM:** every delivery update carries the same header, so nobody else can post fake results.
- `CALLBACK_SECRET` is generated randomly by Render on the CRM and copied to the channel service through `fromService` in `render.yaml`, so you never have to type it.
- If `APP_PASSWORD` / `CALLBACK_SECRET` are empty (local dev), every check is skipped.

---

## 8. Debugging helpers and gotchas

**Helper scripts** (run from `crm-service/`): `check_data.py` (customer spread by city and spend), `check_comms.py` (message statuses of recent campaigns), `diag.py` (raw-SQL status breakdowns). On the channel service, `GET :8001/pending-callbacks` shows callbacks waiting to be retried.

**Things to know:**

- **There are two seed scripts.** `crm-service/seed.py` (used on deploy) skips if customers already exist. `app/db/seed.py` (`python -m app.db.seed`) **always adds 200 more**, so prefer `python seed.py`. Running it twice is how a database ends up with 400 customers.
- **Deleting a segment** keeps its campaigns, but their `segment_id` becomes empty. A *draft* campaign whose segment was deleted will fail when launched.
- **Password protection is one shared password**, not user accounts. Anyone who knows it has full access, so pick a long one and change it in Render if it leaks. Use the site over `https://` (Render's default), never plain `http://`, so the password isn't sent in the clear.
- **Delivery is simulated.** Delivery, open and click outcomes are random, and the 15% conversion is decided by the CRM, not by real customer behaviour.
- **Small timing overlap during launch:** each batch is marked `sent` right after the channel service accepts it. Delivery callbacks arrive at least 1 s later, so in practice they come after it. With a very slow database, a `delivered` update could be overwritten by `sent`.
- **If delivery results never arrive on Render** (campaigns show 0 delivered), the two services can't reach each other. In Render, set `CHANNEL_SERVICE_URL` on brewco-crm-app to the channel service's `https://...onrender.com` address, and `CRM_CALLBACK_URL` on brewco-channel-app to the CRM's address. Also check both have the same `CALLBACK_SECRET`.
- **Build fails with `Name or service not known` during migrations:** `DATABASE_URL` points at a database Render can't find. The free database may have expired, or it's in a different region. Copy the database's *Internal Database URL* into `DATABASE_URL`.
- **Campaign launches run inside the API process.** If the CRM API restarts mid-launch, the remaining batches are not sent and the campaign stays `running`.
