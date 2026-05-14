"""Тесты для ESchoolClient (httpx-сессия + авто-релогин)."""
import httpx
import pytest
import respx

from app.eschool.client import ESchoolClient, EschoolAuthError

BASE = "https://app.eschool.center/ec-server"


@pytest.fixture
def state_response() -> dict:
    return {
        "authenticated": True,
        "userId": 564041,
        "user": {
            "sessionId": 93743164,
            "userId": 564041,
            "prsId": 233819,
            "username": "mrtelnor",
            "currentPosition": {
                "prsId": 233819,
                "prsFio": "Волков Никита Владимирович",
                "posName": "Родитель",
                "myChildren": [{"prsId": 219673, "fio": "Волкова Вероника Никитична"}],
            },
        },
    }


@respx.mock
async def test_client_logs_in_and_loads_state(state_response):
    respx.post(f"{BASE}/login").mock(return_value=httpx.Response(200))
    respx.get(f"{BASE}/state").mock(return_value=httpx.Response(200, json=state_response))

    client = ESchoolClient(login="user", password="pass", base_url=BASE)
    await client.connect()

    assert client.parent_prs_id == 233819
    assert client.children == [{"prsId": 219673, "fio": "Волкова Вероника Никитична"}]
    await client.aclose()


@respx.mock
async def test_client_retries_after_401(state_response):
    """При 401 в запросе getPrsDiary бот должен залогиниться заново и повторить запрос."""
    diary_payload = {"lesson": [], "user": [{"mark": []}]}

    respx.post(f"{BASE}/login").mock(return_value=httpx.Response(200))
    respx.get(f"{BASE}/state").mock(return_value=httpx.Response(200, json=state_response))

    diary_route = respx.get(f"{BASE}/student/getPrsDiary").mock(
        side_effect=[
            httpx.Response(401),
            httpx.Response(200, json=diary_payload),
        ]
    )

    client = ESchoolClient(login="user", password="pass", base_url=BASE)
    await client.connect()
    result = await client.get_diary(prs_id=219673, d1_ms=1, d2_ms=2)

    assert result == diary_payload
    assert diary_route.call_count == 2


@respx.mock
async def test_client_raises_on_repeated_401(state_response):
    respx.post(f"{BASE}/login").mock(return_value=httpx.Response(200))
    respx.get(f"{BASE}/state").mock(return_value=httpx.Response(200, json=state_response))
    respx.get(f"{BASE}/student/getPrsDiary").mock(return_value=httpx.Response(401))

    client = ESchoolClient(login="user", password="pass", base_url=BASE)
    await client.connect()
    with pytest.raises(httpx.HTTPStatusError):
        await client.get_diary(prs_id=219673, d1_ms=1, d2_ms=2)


@respx.mock
async def test_cookies_mode_skips_login(state_response):
    """В cookies-режиме клиент не вызывает /login, только /state с переданными куками."""
    login_route = respx.post(f"{BASE}/login")
    respx.get(f"{BASE}/state").mock(return_value=httpx.Response(200, json=state_response))

    client = ESchoolClient(
        cookie_header="JSESSIONID=abc; es_prs=233819",
        base_url=BASE,
    )
    await client.connect()

    assert login_route.call_count == 0
    assert client.parent_prs_id == 233819
    assert client.cookies_mode is True
    await client.aclose()


@respx.mock
async def test_cookies_mode_raises_auth_error_on_401_state():
    """Если /state вернул 401 — cookies невалидны, EschoolAuthError."""
    respx.get(f"{BASE}/state").mock(return_value=httpx.Response(401))

    client = ESchoolClient(cookie_header="JSESSIONID=stale", base_url=BASE)
    with pytest.raises(EschoolAuthError):
        await client.connect()


@respx.mock
async def test_cookies_mode_raises_auth_error_on_401_diary(state_response):
    """Cookies были валидны на старте, но протухли — get_diary получает 401 → EschoolAuthError.
    В отличие от login/pass режима, повторно логиниться не пытаемся."""
    respx.get(f"{BASE}/state").mock(return_value=httpx.Response(200, json=state_response))
    diary_route = respx.get(f"{BASE}/student/getPrsDiary").mock(return_value=httpx.Response(401))

    client = ESchoolClient(cookie_header="JSESSIONID=abc", base_url=BASE)
    await client.connect()
    with pytest.raises(EschoolAuthError):
        await client.get_diary(prs_id=219673, d1_ms=1, d2_ms=2)

    # Никаких повторных попыток — только один запрос
    assert diary_route.call_count == 1


@respx.mock
async def test_cookies_mode_raises_when_state_returns_unauthenticated():
    """Если /state отвечает 200 но authenticated=false — тоже EschoolAuthError."""
    respx.get(f"{BASE}/state").mock(return_value=httpx.Response(200, json={"authenticated": False}))

    client = ESchoolClient(cookie_header="JSESSIONID=stale", base_url=BASE)
    with pytest.raises(EschoolAuthError):
        await client.connect()
