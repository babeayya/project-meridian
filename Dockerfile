# ── Backend image (FastAPI) ─────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1

# curl is only needed for the container HEALTHCHECK below
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install .

# run as an unprivileged user
RUN useradd --create-home --uid 10001 appuser
USER appuser

# Most hosts (Render, Railway, Fly, Cloud Run) inject $PORT; default to 8000.
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://localhost:${PORT}/api/v1/health" || exit 1

# shell form so ${PORT} expands at runtime
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
