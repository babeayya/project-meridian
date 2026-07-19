# Deploying Meridian

The platform is **two deployable services** plus two stateful dependencies:

| Service | What it is | Needs |
|---|---|---|
| **Backend** (`Dockerfile`) | FastAPI API on port `$PORT` | PostgreSQL; Redis (optional — see below); secrets |
| **Frontend** (`frontend/Dockerfile`) | Next.js standalone server on port `$PORT` | The backend's public URL, baked in at build |
| PostgreSQL | Canonical data store | A managed instance or the compose one |
| Redis | Rate-limit buckets, circuit-breaker state, Celery broker | **Optional** — omit it and the backend falls back to an in-process control plane (`REDIS_URL=memory://`). Only needed for multi-instance or background workers. |

Everything is env-driven and the images build clean today (verified: frontend standalone build + backend prod boot with working CORS).

---

## Read these four things first

1. **Secrets never go in the repo.** Set `OPENROUTER_API_KEY`, `NEWSAPI_API_KEY`, `FMP_API_KEY` in the host's dashboard/secret store. `.dockerignore` already excludes `.env`.
2. **`CORS_ORIGINS` is mandatory in prod.** It must list the exact frontend origin(s), e.g. `https://meridian.vercel.app`. If it's blank, the browser blocks every API call (the backend logs a warning at startup).
3. **`NEXT_PUBLIC_API_BASE` is baked in at BUILD time**, not runtime. Set it before/at build to the backend's public URL **+ `/api/v1`**. Rebuild the frontend whenever the backend URL changes.
4. **Datacenter-IP caveat.** Yahoo Finance often returns 403 to cloud IPs. SEC EDGAR, FMP and NewsAPI are usually fine, so US fundamentals (EDGAR) and news still work, but live quotes/prices (Yahoo) may be flaky from some hosts. Not a bug — a property of free data sources. A VPS lets you pick a friendlier region/IP; serverless platforms are the most affected.

---

## Environment variable matrix

**Backend** (set in host dashboard):

| Variable | Value | Required |
|---|---|---|
| `ENV` | `prod` | yes |
| `DATABASE_URL` | `postgresql+asyncpg://USER:PASS@HOST:5432/DB` | yes |
| `CORS_ORIGINS` | your frontend URL(s), comma-separated | yes |
| `REDIS_URL` | `redis://…` or leave unset (`memory://`) | no |
| `OPENROUTER_API_KEY` | AI agents + news classification | for AI/news |
| `NEWSAPI_API_KEY`, `FMP_API_KEY` | data providers | recommended |
| `LLM_MODEL_ANALYSIS`, `LLM_MODEL_CLASSIFY` | model ids | optional |
| `SEC_EDGAR_USER_AGENT` | `"Meridian your-email@example.com"` | recommended |
| `API_KEYS` | comma-separated keys for `X-API-Key` gate | see "Locking down" |

`PORT` is injected automatically by Render/Railway/Fly/Cloud Run — the Dockerfile binds to it.

**Frontend** (set at build time):

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_BASE` | `https://<your-backend-url>/api/v1` |

---

## Path A — Any Docker host / VPS (self-contained, most robust)

Best control over region/IP for the Yahoo caveat, and the only path that runs the Celery worker.

```bash
# on the server, in the repo root
cp .env.example .env          # fill in the API keys
# edit docker-compose.yml: set the two URLs marked <<< to your domain
docker compose up --build -d
```

This starts Postgres, Redis, the API (:8000), the Celery worker, and the frontend (:3000). Put **Caddy** in front for automatic HTTPS:

```
# /etc/caddy/Caddyfile
api.yourdomain.com { reverse_proxy localhost:8000 }
yourdomain.com     { reverse_proxy localhost:3000 }
```

Then build the frontend with `NEXT_PUBLIC_API_BASE=https://api.yourdomain.com/api/v1` and set the API's `CORS_ORIGINS=https://yourdomain.com`.

## Path B — Managed split (Render/Railway backend + Vercel frontend)

**Backend (Render example):**
1. New → Web Service → connect the repo → it detects the `Dockerfile`.
2. Add a **PostgreSQL** instance; copy its internal URL into `DATABASE_URL` (prefix the driver: `postgresql+asyncpg://…`).
3. Set env vars from the matrix above, including `CORS_ORIGINS` (fill in after the Vercel step) and your API keys.
4. Deploy. Smoke-test `https://<backend>/api/v1/health` → `{"status":"ok"}`.
   (Railway is the same shape; it can also host Postgres + Redis in the same project.)

**Frontend (Vercel):**
1. New Project → import the repo → **Root Directory = `frontend`**.
2. Env var `NEXT_PUBLIC_API_BASE = https://<backend>/api/v1`.
3. Deploy → you get `https://<app>.vercel.app`.
4. Go back and set the backend's `CORS_ORIGINS` to that Vercel URL; redeploy the backend.

> Free-tier notes: Render's free web service **sleeps after ~15 min idle** (first request then takes ~30 s to wake) and free Postgres expires after ~90 days. Railway is usage-based with a small monthly credit. Fine for a demo; upgrade for always-on.

## Path C — Google Cloud Run (serverless, scales to zero)

`gcloud run deploy` the backend image (set env vars + a Cloud SQL Postgres), then the frontend image with the `NEXT_PUBLIC_API_BASE` build arg. Most affected by the Yahoo datacenter-IP caveat.

---

## Post-deploy smoke test

```bash
curl https://<backend>/api/v1/health                 # {"status":"ok"}
curl https://<backend>/api/v1/health/providers        # 7 providers listed
# open the frontend, press Ctrl+K, search "Apple" → dashboard should load
# on the company page press "Refresh data" once to ingest fundamentals
```

If search returns nothing: the frontend's `NEXT_PUBLIC_API_BASE` is wrong or CORS is blocking — check the browser console and the backend's startup `cors_origins_empty_in_prod` warning.

---

## Locking down (important for a public URL)

The API currently has **no per-user auth** — with your keys set, anyone who finds the URL can run analyses and burn your OpenRouter/NewsAPI/FMP quotas. Options:

- **Demo, simplest:** leave it open but keep provider quotas small; optionally rate-limit at the proxy (Caddy/Cloudflare).
- **Service-key gate:** set `API_KEYS=<random>` on the backend. Note the current frontend does **not** send `X-API-Key`, and because it's a public SPA any key it holds is visible — so this deters casual abuse only, not a determined user. Real multi-user auth (per-user login, server-side key custody) is the next build step.

---

## What's not yet automated

- **Alembic migrations** — the app currently `create_all`s tables on startup, which is fine for first deploy but you'll want migrations before schema changes ship to a live DB.
- **Celery beat schedules** — background refresh isn't scheduled yet; ingestion is on-demand via the API.
- **CDN/caching** for chart endpoints.

These are noted in `docs/07-roadmap.md`.
