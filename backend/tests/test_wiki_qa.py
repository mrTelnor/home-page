"""Вики /api/wiki/*: дополнительные проверки QA к test_wiki.py.

Порядок «права → база знаний», настоящий engine при недоступной базе (ответ и лог
без пароля), крайние случаи slug, неизменность текста SQL, соседние лимиты и CORS.
В Supabase тесты не ходят: настоящий engine стучится в закрытый порт 127.0.0.1.
"""
import logging

import pytest
from httpx import AsyncClient

from app.core import ratelimit, wiki_db
from app.core.config import settings
from app.core.ratelimit import limiter
from app.services import wiki as wiki_service
from tests.test_wiki import (
    DETAIL,
    NOTEBOOK_ID,
    PROTECTED_PATHS,
    SUMMARY,
    FakeConn,
    FakeEngine,
)

DB_PASSWORD = "qa-Pa55w0rd-do-not-leak"
# Порт 1 на localhost закрыт: соединение отклоняется сразу, сеть не нужна
UNREACHABLE_DSN = f"postgresql+asyncpg://wiki_reader.projectref:{DB_PASSWORD}@127.0.0.1:1/postgres"


@pytest.fixture
def engine_spy(monkeypatch) -> list[str]:
    """Считает обращения к engine базы знаний."""
    calls: list[str] = []

    def spy():
        calls.append("get_wiki_engine")
        return FakeEngine()

    monkeypatch.setattr(wiki_db, "get_wiki_engine", spy)
    return calls


@pytest.fixture
async def real_unreachable_engine(monkeypatch):
    """Настоящий engine SQLAlchemy/asyncpg с паролем в строке подключения и закрытым портом."""
    monkeypatch.setattr(wiki_db, "_engine", None)
    monkeypatch.setattr(settings, "wiki_database_url", UNREACHABLE_DSN)
    yield
    await wiki_db.dispose_wiki_engine()


@pytest.fixture
def slug_calls(monkeypatch) -> list[str]:
    """Сервис заметки подменён: запоминает slug, который дошёл до слоя данных."""
    calls: list[str] = []

    async def get_note_by_slug(conn, slug):
        calls.append(slug)
        return {**DETAIL, "slug": slug}

    monkeypatch.setattr(wiki_db, "get_wiki_engine", lambda: FakeEngine())
    monkeypatch.setattr(wiki_service, "get_note_by_slug", get_note_by_slug)
    return calls


@pytest.fixture
def enabled_limiter():
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.enabled = False
    limiter.reset()


# --- Права проверяются раньше обращения к базе знаний ---


@pytest.mark.parametrize("path", PROTECTED_PATHS)
async def test_guest_never_touches_wiki_db(client: AsyncClient, engine_spy, path: str):
    """База «доступна», но гость до неё не доходит."""
    response = await client.get(path)

    assert response.status_code == 401
    assert engine_spy == []


@pytest.mark.parametrize("path", PROTECTED_PATHS)
async def test_user_never_touches_wiki_db(authed_client: AsyncClient, engine_spy, path: str):
    response = await authed_client.get(path)

    assert response.status_code == 403
    assert engine_spy == []


async def test_invalid_token_never_touches_wiki_db(client: AsyncClient, engine_spy):
    response = await client.get("/api/wiki/recent", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401
    assert engine_spy == []


# --- Настоящий engine, база недоступна: 503 / health 200, пароля нет ни в ответе, ни в логе ---


def _assert_no_secret(text: str) -> None:
    assert DB_PASSWORD not in text
    assert UNREACHABLE_DSN not in text


@pytest.mark.parametrize("path", PROTECTED_PATHS)
async def test_real_engine_unreachable_returns_503_without_secret(
    admin_client: AsyncClient, real_unreachable_engine, caplog, path: str
):
    caplog.set_level(logging.DEBUG)

    response = await admin_client.get(path)

    assert response.status_code == 503
    assert response.json() == {"detail": "Wiki database is unavailable"}
    _assert_no_secret(response.text)
    _assert_no_secret(str(response.headers))
    # caplog.text включает отформатированный traceback из logger.exception
    assert "Wiki database request failed" in caplog.text
    _assert_no_secret(caplog.text)


async def test_real_engine_unreachable_health_is_200_without_secret(
    client: AsyncClient, real_unreachable_engine, caplog
):
    caplog.set_level(logging.DEBUG)

    response = await client.get("/api/wiki/health")

    assert response.status_code == 200
    assert response.json() == {"status": "unavailable"}
    _assert_no_secret(response.text)
    _assert_no_secret(caplog.text)


async def test_real_engine_pool_fits_role_connection_limit(real_unreachable_engine):
    """Проверяем сам пул настоящего engine, а не аргументы подменённого конструктора."""
    pool = wiki_db.get_wiki_engine().pool

    # У роли wiki_reader лимит 6 соединений; при пересоздании контейнера живут два пула
    assert pool.size() + pool._max_overflow <= 3


# --- slug: крайние случаи и порядок маршрутов ---


async def test_note_slug_percent_encoded_slash(admin_client: AsyncClient, slug_calls):
    """%2F в пути декодируется в «/» — slug тот же, что и с обычным слэшем."""
    response = await admin_client.get("/api/wiki/notes/moi-domashnii-sait%2Fgrabli")

    assert response.status_code == 200
    assert slug_calls == ["moi-domashnii-sait/grabli"]


@pytest.mark.parametrize("slug", ["search", "recent", "health", "notebooks", "notes/notes"])
async def test_note_slug_equal_to_route_name(admin_client: AsyncClient, slug_calls, slug: str):
    """Заметка со slug, совпадающим с именем другого маршрута, читается как заметка."""
    response = await admin_client.get(f"/api/wiki/notes/{slug}")

    assert response.status_code == 200
    assert slug_calls == [slug]


@pytest.mark.parametrize("path", ["/api/wiki/search?q=x", "/api/wiki/recent", "/api/wiki/notebooks", "/api/wiki/health"])
async def test_note_route_does_not_capture_other_paths(admin_client: AsyncClient, slug_calls, path: str):
    """Маршрут /notes/{slug:path} не перехватывает соседние пути."""
    await admin_client.get(path)

    assert slug_calls == []


async def test_note_very_long_slug_is_not_500(admin_client: AsyncClient, slug_calls):
    slug = "/".join(["a" * 50] * 80)  # ~4 КБ

    response = await admin_client.get(f"/api/wiki/notes/{slug}")

    assert response.status_code == 200
    assert slug_calls == [slug]


@pytest.mark.parametrize(
    "slug",
    ["../../etc/passwd", "a/../b", "..", "x' or '1'='1", "a%2Fb", "a\\b", "x; drop table notes; --", "a" * 5000],
)
async def test_get_note_by_slug_sql_does_not_depend_on_slug(slug: str):
    """slug уходит только параметром: текст SQL одинаков для любого значения."""
    reference = FakeConn(results=[[]])
    await wiki_service.get_note_by_slug(reference, "moi-domashnii-sait/grabli")
    conn = FakeConn(results=[[]])

    assert await wiki_service.get_note_by_slug(conn, slug) is None

    assert [sql for sql, _ in conn.calls] == [sql for sql, _ in reference.calls]
    assert conn.calls[0][1] == {"slug": slug}
    assert slug not in conn.calls[0][0]


# --- Параметризация: текст SQL не зависит от ввода ---


async def test_search_sql_does_not_depend_on_values():
    evil = "x' or 1=1 --"
    safe = FakeConn()
    hostile = FakeConn()

    await wiki_service.search_notes(safe, q="docker", project="home-page", note_type="runbook", tag="k8s", limit=5)
    await wiki_service.search_notes(hostile, q=evil, project=evil, note_type=evil, tag=evil, limit=5)

    assert hostile.calls[0][0] == safe.calls[0][0]
    assert "1=1" not in hostile.calls[0][0]
    assert hostile.calls[0][1]["tsquery"] == "x:* & or:* & 1:* & 1:*"


async def test_all_service_statements_are_selects():
    """Сервис только читает: каждый запрос начинается с select и не содержит изменяющих команд."""
    note_row = {
        "id": SUMMARY["id"], "slug": "a/b", "title": "T", "content": "C", "metadata": {},
        "created_at": SUMMARY["updated_at"], "updated_at": SUMMARY["updated_at"],
        "notebook_id": None, "notebook_name": None, "notebook_slug": None, "tags": [],
    }
    conn = FakeConn(results=[[], [{"?column?": 1}], [], [note_row], [], [], [], []])

    await wiki_service.get_notebook_tree(conn)
    await wiki_service.get_notebook_notes(conn, NOTEBOOK_ID)
    await wiki_service.get_note_by_slug(conn, "a/b")
    await wiki_service.search_notes(conn, q="x", project="p", note_type="t", tag="g", limit=1)
    await wiki_service.get_recent_notes(conn, 1)

    assert len(conn.calls) == 8
    for sql, _ in conn.calls:
        words = sql.lower().split()
        assert words[0] == "select"
        assert not {"insert", "update", "delete", "drop", "truncate", "alter", "create", "grant", "copy"} & set(words)
        assert ";" not in sql


# --- Rate limit ---


def test_limits_values():
    """Лимит вики — 120/мин; существующие лимиты не изменились."""
    assert ratelimit.WIKI_LIMIT == "120/minute"
    assert ratelimit.LOGIN_LIMIT == "10/minute"
    assert ratelimit.REGISTER_LIMIT == "5/minute"
    assert ratelimit.PASSWORD_RESET_LIMIT == "5/minute"


async def test_health_does_not_consume_wiki_limit(client: AsyncClient, enabled_limiter):
    headers = {"X-Real-Ip": "203.0.113.50"}

    for _ in range(130):
        response = await client.get("/api/wiki/health", headers=headers)
        assert response.status_code == 200

    response = await client.get("/api/wiki/recent", headers=headers)
    assert response.status_code == 401


async def test_wiki_limit_applies_to_admin(admin_client: AsyncClient, slug_calls, enabled_limiter):
    """Лимит действует и на авторизованного админа: 120 ответов 200, затем 429."""
    headers = {"X-Real-Ip": "203.0.113.51"}

    for i in range(120):
        response = await admin_client.get("/api/wiki/notes/a/b", headers=headers)
        assert response.status_code == 200, f"запрос {i + 1}: {response.status_code}"

    response = await admin_client.get("/api/wiki/notes/a/b", headers=headers)
    assert response.status_code == 429
    assert len(slug_calls) == 120


async def test_wiki_limit_does_not_touch_login_limit(client: AsyncClient, enabled_limiter):
    """Исчерпанный лимит вики не блокирует вход с того же IP, и лимит входа остался 10/мин."""
    headers = {"X-Real-Ip": "203.0.113.52"}
    for _ in range(121):
        await client.get("/api/wiki/recent", headers=headers)
    assert (await client.get("/api/wiki/recent", headers=headers)).status_code == 429

    body = {"username": "nobody", "password": "wrong-password"}
    for i in range(10):
        response = await client.post("/api/auth/login", json=body, headers=headers)
        assert response.status_code == 401, f"вход {i + 1}: {response.status_code}"
    response = await client.post("/api/auth/login", json=body, headers=headers)
    assert response.status_code == 429


# --- CORS ---


async def test_cors_default_origins_are_exactly_site_and_wiki():
    from starlette.middleware.cors import CORSMiddleware

    from app.main import app

    cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)

    assert settings.cors_origins is None
    assert sorted(cors.kwargs["allow_origins"]) == sorted(
        [f"https://{settings.domain}", f"https://wiki.{settings.domain}"]
    )
    assert cors.kwargs["allow_credentials"] is True


async def test_cors_main_origin_unchanged_for_existing_api(client: AsyncClient):
    origin = f"https://{settings.domain}"

    response = await client.options(
        "/api/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"


async def test_cors_actual_request_from_wiki_origin(client: AsyncClient):
    """Обычный (не preflight) запрос с origin вики получает заголовки CORS."""
    origin = f"https://wiki.{settings.domain}"

    response = await client.get("/api/wiki/health", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"


@pytest.mark.parametrize(
    "origin_template",
    ["http://wiki.{domain}", "https://wiki.{domain}.evil.example", "https://evilwiki.{domain}", "https://wiki.{domain}:8443"],
)
async def test_cors_lookalike_origins_get_no_headers(client: AsyncClient, origin_template: str):
    origin = origin_template.format(domain=settings.domain)

    response = await client.get("/api/wiki/health", headers={"Origin": origin})

    assert "access-control-allow-origin" not in response.headers
