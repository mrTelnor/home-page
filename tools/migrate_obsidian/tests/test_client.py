import httpx
import pytest
import respx

from migrate_obsidian.auth import TokenManager
from migrate_obsidian.client import PostgRESTClient


def make_tm(token: str = "tok") -> TokenManager:
    tm = TokenManager(backend_url="https://backend", username="u", password="p")
    tm._token = token
    return tm


@respx.mock
async def test_create_notebook():
    respx.post("https://knowledge/notebooks").mock(
        return_value=httpx.Response(201, json=[{"id": "n1", "name": "n", "slug": "n"}])
    )
    client = PostgRESTClient(base_url="https://knowledge", token_manager=make_tm())
    nb = await client.create_notebook(name="n", slug="n")
    assert nb["id"] == "n1"


@respx.mock
async def test_client_refreshes_on_401():
    respx.post("https://knowledge/notebooks").mock(side_effect=[
        httpx.Response(401, text="JWT expired"),
        httpx.Response(201, json=[{"id": "n1", "name": "n", "slug": "n"}]),
    ])
    respx.post("https://backend/api/auth/knowledge-token").mock(return_value=httpx.Response(
        200, json={"access_token": "tok-refreshed", "token_type": "bearer", "expires_in": 86400}
    ))
    tm = TokenManager(backend_url="https://backend", username="u", password="p")
    tm._token = "tok-old"
    client = PostgRESTClient(base_url="https://knowledge", token_manager=tm)
    nb = await client.create_notebook(name="n", slug="n")
    assert nb["id"] == "n1"
    assert tm._token == "tok-refreshed"
