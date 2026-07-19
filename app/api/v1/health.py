from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import ContainerDep

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(container: ContainerDep) -> dict:
    checks: dict[str, str] = {}
    try:
        async with container.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
    checks["control_plane"] = (
        "ok" if await container.control.ping()
        else "degraded (memory fallback active)"
    )
    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}


@router.get("/health/providers")
async def providers(container: ContainerDep) -> dict:
    return {"providers": await container.registry.health()}
