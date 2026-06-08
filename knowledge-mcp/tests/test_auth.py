import httpx
import respx

from knowledge_mcp.auth import TokenManager


@respx.mock
async def test_token_manager_caches():
    route = respx.post("https://backend/api/auth/knowledge-token").mock(
        return_value=httpx.Response(200, json={
            "access_token": "tok-1", "token_type": "bearer", "expires_in": 86400,
        })
    )
    tm = TokenManager(backend_url="https://backend", username="u", password="p")
    assert await tm.token() == "tok-1"
    assert await tm.token() == "tok-1"
    assert route.call_count == 1
    await tm.aclose()


@respx.mock
async def test_token_manager_force_refresh():
    respx.post("https://backend/api/auth/knowledge-token").mock(side_effect=[
        httpx.Response(200, json={"access_token": "tok-1", "token_type": "bearer", "expires_in": 86400}),
        httpx.Response(200, json={"access_token": "tok-2", "token_type": "bearer", "expires_in": 86400}),
    ])
    tm = TokenManager(backend_url="https://backend", username="u", password="p")
    assert await tm.token() == "tok-1"
    assert await tm.token(force_refresh=True) == "tok-2"
    await tm.aclose()
