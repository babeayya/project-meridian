from celery import Celery

from app.core.config import get_settings

settings = get_settings()

broker = settings.redis_url
if broker.startswith("memory://"):
    # Celery's in-memory broker is for local experimentation only; scheduled
    # ingestion requires Redis (docker-compose provides it).
    broker = "memory://"

celery_app = Celery(
    "equity_research",
    broker=broker,
    backend=None if broker == "memory://" else settings.redis_url,
    include=["app.workers.tasks.ingestion"],
)

celery_app.conf.update(
    task_routes={"app.workers.tasks.ingestion.*": {"queue": "ingestion"}},
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
)
