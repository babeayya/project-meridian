import httpx
import pytest

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
async def client(tmp_path):
    settings = Settings(
        _env_file=None,
        env="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        redis_url="memory://",
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    # lifespan must run so the container is built
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as c:
            yield c


async def test_liveness(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_readiness_reports_db_and_control_plane(client):
    resp = await client.get("/api/v1/health/ready")
    body = resp.json()
    assert resp.status_code == 200
    assert body["checks"]["database"] == "ok"


async def test_provider_registry_exposed(client):
    resp = await client.get("/api/v1/health/providers")
    providers = {p["provider"] for p in resp.json()["providers"]}
    assert {"yahoo", "stooq"} <= providers


async def test_unknown_company_is_problem_json(client):
    resp = await client.get("/api/v1/companies/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")
