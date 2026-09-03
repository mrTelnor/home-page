from httpx import AsyncClient
from sqlalchemy.exc import OperationalError


async def test_health_returns_ok(client: AsyncClient):
    response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


async def test_health_error_does_not_leak_exception(client: AsyncClient, monkeypatch):
    """При сбое БД 503 не должен раскрывать детали исключения (DSN, хост, юзер, имя БД)."""
    from app.api import health

    secret_dsn = "postgresql://homepage:s3cr3t@10.0.0.5:5432/homepage_prod"

    def boom(*args, **kwargs):
        raise OperationalError(
            f"connection to {secret_dsn} failed", params=None, orig=Exception(secret_dsn)
        )

    monkeypatch.setattr(health, "async_session", boom)

    response = await client.get("/api/health")
    assert response.status_code == 503
    body = response.text
    assert "s3cr3t" not in body
    assert "10.0.0.5" not in body
    assert "homepage_prod" not in body
    assert response.json() == {"status": "error"}
