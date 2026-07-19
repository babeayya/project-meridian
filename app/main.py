"""FastAPI application factory."""
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.container import build_container
from app.core.database import init_db
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging

log = structlog.get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.env)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        container = await build_container(settings)
        await init_db(container.engine)
        app.state.container = container
        if not settings.api_key_list and settings.env != "dev":
            log.warning("api_auth_disabled_outside_dev")
        log.info("startup_complete", env=settings.env,
                 providers=list(container.registry.adapters))
        yield
        await container.aclose()

    app = FastAPI(
        title="Equity Research & Valuation Platform",
        version="0.1.0",
        description=(
            "Institutional-grade equity research backend: multi-source data "
            "ingestion with fallback chains, auditable valuation engine, "
            "quant analytics, and AI analysis pipeline."
        ),
        lifespan=lifespan,
    )

    # Dev allows any origin; prod allows exactly the configured frontend
    # origin(s). If prod is misconfigured (no CORS_ORIGINS), warn loudly rather
    # than silently blocking every browser request.
    cors_origins = ["*"] if settings.env == "dev" else settings.cors_origin_list
    if settings.env != "dev" and not cors_origins:
        log.warning("cors_origins_empty_in_prod",
                    hint="set CORS_ORIGINS to your frontend URL or the browser "
                         "will block all API calls")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
        response.headers["X-Request-ID"] = request_id
        return response

    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
