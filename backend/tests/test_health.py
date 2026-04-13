from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient):
    response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
