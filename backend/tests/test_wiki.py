"""Вики /api/wiki/*: доступ, ответы при недоступной базе, health, поиск, CORS.

В Supabase тесты не ходят: вместо engine базы знаний подставляется заглушка,
а функции сервиса в тестах роутера заменяются на возвращающие готовые данные.
"""
import logging
import traceback
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError

from app.api import wiki as wiki_api
from app.core import wiki_db
from app.core.config import settings
from app.core.ratelimit import limiter
from app.services import wiki as wiki_service

NOTEBOOK_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
NOTE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)

SECRET_DSN = "postgresql+asyncpg://wiki_reader.ref:s3cr3t@pooler.example:5432/postgres"

PROTECTED_PATHS = [
    "/api/wiki/notebooks",
    f"/api/wiki/notebooks/{NOTEBOOK_ID}/notes",
    "/api/wiki/notes/moi-domashnii-sait/grabli",
    "/api/wiki/search?q=грабли",
    "/api/wiki/recent",
]

SUMMARY = {
    "id": NOTE_ID,
    "slug": "moi-domashnii-sait/grabli",
    "title": "Грабли home-page",
    "notebook_id": NOTEBOOK_ID,
    "metadata": {"type": "reference", "project": "home-page"},
    "tags": ["docker"],
    "updated_at": NOW,
}

DETAIL = {
    "id": NOTE_ID,
    "slug": "moi-domashnii-sait/grabli",
    "title": "Грабли home-page",
    "content": "# Грабли\n\n<script>alert(1)</script>",
    "metadata": {"type": "reference", "project": "home-page"},
    "notebook": {"id": NOTEBOOK_ID, "name": "Мой домашний сайт", "slug": "moi-domashnii-sait"},
    "tags": ["docker"],
    "links": [{"slug": "moi-domashnii-sait/readme", "title": "README", "alias": None}],
    "backlinks": [{"slug": "moi-domashnii-sait/arhitektura", "title": "Архитектура", "alias": "грабли"}],
    "created_at": NOW,
    "updated_at": NOW,
}

TREE = [
    {
        "id": uuid.UUID("33333333-3333-3333-3333-333333333333"),
        "name": "Пет-проекты",
        "slug": "pet-proekty",
        "parent_id": None,
        "note_count": 0,
        "total_note_count": 30,
        "children": [
            {
                "id": NOTEBOOK_ID,
                "name": "Мой домашний сайт",
                "slug": "moi-domashnii-sait",
                "parent_id": uuid.UUID("33333333-3333-3333-3333-333333333333"),
                "note_count": 30,
                "total_note_count": 30,
                "children": [],
            }
        ],
    }
]


# --- Заглушки слоя данных ---


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class FakeConn:
    """Соединение-заглушка: запоминает запросы и отдаёт заранее заданные строки."""

    def __init__(self, results=None, error=None):
        self.calls: list[tuple[str, dict | None]] = []
        self._results = list(results or [])
        self._error = error

    async def execute(self, statement, params=None):
        self.calls.append((str(statement), params))
        if self._error is not None:
            raise self._error
        return FakeResult(self._results.pop(0) if self._results else [])


class FakeEngine:
    """Engine-заглушка: connect() отдаёт FakeConn либо падает как недоступная база."""

    def __init__(self, conn=None, connect_error=None):
        self.conn = conn or FakeConn()
        self._connect_error = connect_error
        self.disposed = False

    def connect(self):
        engine = self

        class _Ctx:
            async def __aenter__(self):
                if engine._connect_error is not None:
                    raise engine._connect_error
                return engine.conn

            async def __aexit__(self, *exc_info):
                return False

        return _Ctx()

    async def dispose(self):
        self.disposed = True


def _db_error() -> OperationalError:
    return OperationalError(f"connection to {SECRET_DSN} failed", params=None, orig=Exception(SECRET_DSN))


@pytest.fixture
def wiki_engine(monkeypatch) -> FakeEngine:
    """База знаний «доступна»: engine подменён заглушкой."""
    engine = FakeEngine()
    monkeypatch.setattr(wiki_db, "get_wiki_engine", lambda: engine)
    return engine


@pytest.fixture
def wiki_data(monkeypatch, wiki_engine) -> dict:
    """Сервис вики возвращает готовые данные; вызовы запоминаются."""
    calls: dict = {}

    async def get_notebook_tree(conn):
        return TREE

    async def get_notebook_notes(conn, notebook_id):
        calls["notebook_id"] = notebook_id
        return [SUMMARY] if notebook_id == NOTEBOOK_ID else None

    async def get_note_by_slug(conn, slug):
        calls["slug"] = slug
        return {**DETAIL, "slug": slug} if slug != "net/takoi" else None

    async def search_notes(conn, q, project, note_type, tag, limit):
        calls["search"] = {"q": q, "project": project, "note_type": note_type, "tag": tag, "limit": limit}
        return [SUMMARY]

    async def get_recent_notes(conn, limit):
        calls["recent_limit"] = limit
        return [SUMMARY]

    for fn in (get_notebook_tree, get_notebook_notes, get_note_by_slug, search_notes, get_recent_notes):
        monkeypatch.setattr(wiki_service, fn.__name__, fn)
    return calls


# --- Доступ ---


@pytest.mark.parametrize("path", PROTECTED_PATHS)
async def test_guest_gets_401(client: AsyncClient, path: str):
    """Гость → 401, причём раньше обращения к базе знаний (вики в тестах выключена)."""
    response = await client.get(path)
    assert response.status_code == 401


@pytest.mark.parametrize("path", PROTECTED_PATHS)
async def test_user_gets_403(authed_client: AsyncClient, path: str):
    response = await authed_client.get(path)
    assert response.status_code == 403


@pytest.mark.parametrize("path", PROTECTED_PATHS)
async def test_admin_gets_200(admin_client: AsyncClient, wiki_data, path: str):
    response = await admin_client.get(path)
    assert response.status_code == 200, response.text


# --- Ответы ---


async def test_notebooks_tree(admin_client: AsyncClient, wiki_data):
    response = await admin_client.get("/api/wiki/notebooks")
    data = response.json()

    assert data[0]["name"] == "Пет-проекты"
    assert data[0]["total_note_count"] == 30
    child = data[0]["children"][0]
    assert child["id"] == str(NOTEBOOK_ID)
    assert child["parent_id"] == data[0]["id"]
    assert child["note_count"] == 30
    assert child["children"] == []


async def test_notebook_notes(admin_client: AsyncClient, wiki_data):
    response = await admin_client.get(f"/api/wiki/notebooks/{NOTEBOOK_ID}/notes")

    assert wiki_data["notebook_id"] == NOTEBOOK_ID
    assert response.json() == [
        {
            "id": str(NOTE_ID),
            "slug": "moi-domashnii-sait/grabli",
            "title": "Грабли home-page",
            "notebook_id": str(NOTEBOOK_ID),
            "metadata": {"type": "reference", "project": "home-page"},
            "tags": ["docker"],
            "updated_at": "2026-10-05T12:00:00Z",
        }
    ]


async def test_notebook_not_found(admin_client: AsyncClient, wiki_data):
    response = await admin_client.get(f"/api/wiki/notebooks/{uuid.uuid4()}/notes")
    assert response.status_code == 404
    assert response.json() == {"detail": "Notebook not found"}


async def test_notebook_id_must_be_uuid(admin_client: AsyncClient, wiki_data):
    response = await admin_client.get("/api/wiki/notebooks/not-a-uuid/notes")
    assert response.status_code == 422


@pytest.mark.parametrize(
    "slug",
    ["readme", "moi-domashnii-sait/grabli", "rabochie-zametki/anyflow-zone-migrations/2026-09-runbook"],
)
async def test_note_slug_with_slashes(admin_client: AsyncClient, wiki_data, slug: str):
    """slug заметки содержит «/» — в сервис он должен прийти целиком."""
    response = await admin_client.get(f"/api/wiki/notes/{slug}")

    assert response.status_code == 200
    assert wiki_data["slug"] == slug
    assert response.json()["slug"] == slug


async def test_note_detail_shape(admin_client: AsyncClient, wiki_data):
    response = await admin_client.get("/api/wiki/notes/moi-domashnii-sait/grabli")
    data = response.json()

    assert set(data) == {
        "id", "slug", "title", "content", "metadata", "notebook", "tags",
        "links", "backlinks", "created_at", "updated_at",
    }
    # Контент отдаётся как есть: сырой HTML обезвреживает фронтенд при отрисовке
    assert data["content"] == "# Грабли\n\n<script>alert(1)</script>"
    assert data["notebook"] == {"id": str(NOTEBOOK_ID), "name": "Мой домашний сайт", "slug": "moi-domashnii-sait"}
    assert data["links"] == [{"slug": "moi-domashnii-sait/readme", "title": "README", "alias": None}]
    assert data["backlinks"] == [
        {"slug": "moi-domashnii-sait/arhitektura", "title": "Архитектура", "alias": "грабли"}
    ]


async def test_note_not_found(admin_client: AsyncClient, wiki_data):
    response = await admin_client.get("/api/wiki/notes/net/takoi")
    assert response.status_code == 404
    assert response.json() == {"detail": "Note not found"}


async def test_search_passes_filters(admin_client: AsyncClient, wiki_data):
    response = await admin_client.get(
        "/api/wiki/search",
        params={"q": "грабли docker", "project": "home-page", "type": "reference", "tag": "docker", "limit": 5},
    )

    assert response.status_code == 200
    assert wiki_data["search"] == {
        "q": "грабли docker",
        "project": "home-page",
        "note_type": "reference",
        "tag": "docker",
        "limit": 5,
    }


async def test_search_defaults(admin_client: AsyncClient, wiki_data):
    await admin_client.get("/api/wiki/search")
    assert wiki_data["search"] == {
        "q": None,
        "project": None,
        "note_type": None,
        "tag": None,
        "limit": wiki_api.SEARCH_LIMIT_DEFAULT,
    }


@pytest.mark.parametrize(
    "query",
    ["limit=0", f"limit={wiki_api.LIST_LIMIT_MAX + 1}", "limit=abc", "q=" + "я" * (wiki_api.SEARCH_QUERY_MAX_LENGTH + 1)],
)
async def test_search_validation(admin_client: AsyncClient, wiki_data, query: str):
    response = await admin_client.get(f"/api/wiki/search?{query}")
    assert response.status_code == 422


async def test_recent_limit(admin_client: AsyncClient, wiki_data):
    await admin_client.get("/api/wiki/recent")
    assert wiki_data["recent_limit"] == wiki_api.RECENT_LIMIT_DEFAULT

    await admin_client.get("/api/wiki/recent?limit=7")
    assert wiki_data["recent_limit"] == 7

    response = await admin_client.get(f"/api/wiki/recent?limit={wiki_api.LIST_LIMIT_MAX + 1}")
    assert response.status_code == 422


# --- Недоступная база: 503, а не 500 ---


@pytest.mark.parametrize("path", PROTECTED_PATHS)
async def test_disabled_wiki_returns_503(admin_client: AsyncClient, path: str):
    """Пустой WIKI_DATABASE_URL — вики выключена."""
    assert settings.wiki_database_url == ""

    response = await admin_client.get(path)
    assert response.status_code == 503
    assert response.json() == {"detail": "Wiki is disabled"}


@pytest.mark.parametrize("path", PROTECTED_PATHS)
async def test_connect_failure_returns_503(admin_client: AsyncClient, monkeypatch, path: str):
    """Нет связи с Supabase (или проект на паузе) — 503 без деталей подключения."""
    monkeypatch.setattr(wiki_db, "get_wiki_engine", lambda: FakeEngine(connect_error=_db_error()))

    response = await admin_client.get(path)
    assert response.status_code == 503
    assert response.json() == {"detail": "Wiki database is unavailable"}
    assert "s3cr3t" not in response.text
    assert "pooler.example" not in response.text


@pytest.mark.parametrize("error", [_db_error(), TimeoutError(), ConnectionRefusedError()])
async def test_query_failure_returns_503(admin_client: AsyncClient, monkeypatch, error: Exception):
    """Сбой уже во время запроса (обрыв, таймаут) — тоже 503."""
    engine = FakeEngine(conn=FakeConn(error=error))
    monkeypatch.setattr(wiki_db, "get_wiki_engine", lambda: engine)

    response = await admin_client.get("/api/wiki/recent")
    assert response.status_code == 503
    assert response.json() == {"detail": "Wiki database is unavailable"}
    assert "s3cr3t" not in response.text


# --- Health ---


async def test_health_disabled(client: AsyncClient):
    response = await client.get("/api/wiki/health")
    assert response.status_code == 200
    assert response.json() == {"status": "disabled"}


async def test_health_ok_is_public(client: AsyncClient, wiki_engine: FakeEngine):
    """Без авторизации; в базе выполняется select 1."""
    response = await client.get("/api/wiki/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert [sql.strip().lower() for sql, _ in wiki_engine.conn.calls] == ["select 1"]


@pytest.mark.parametrize("failure", ["connect", "query"])
async def test_health_unavailable(client: AsyncClient, monkeypatch, failure: str):
    """База недоступна — всё равно 200, только статус, без деталей."""
    if failure == "connect":
        engine = FakeEngine(connect_error=_db_error())
    else:
        engine = FakeEngine(conn=FakeConn(error=_db_error()))
    monkeypatch.setattr(wiki_db, "get_wiki_engine", lambda: engine)

    response = await client.get("/api/wiki/health")
    assert response.status_code == 200
    assert response.json() == {"status": "unavailable"}
    assert "s3cr3t" not in response.text


# --- Engine базы знаний ---


@pytest.fixture
def reset_wiki_engine(monkeypatch):
    monkeypatch.setattr(wiki_db, "_engine", None)
    yield
    wiki_db._engine = None


def test_engine_not_created_when_disabled(monkeypatch, reset_wiki_engine):
    def fail(*args, **kwargs):
        raise AssertionError("engine не должен создаваться при пустом WIKI_DATABASE_URL")

    monkeypatch.setattr(wiki_db, "create_async_engine", fail)

    with pytest.raises(wiki_db.WikiDisabledError):
        wiki_db.get_wiki_engine()


async def test_engine_created_lazily_with_pool_limits_and_ssl(monkeypatch, reset_wiki_engine):
    created: list[tuple[str, dict]] = []

    def fake_create(url, **kwargs):
        created.append((url, kwargs))
        return FakeEngine()

    monkeypatch.setattr(wiki_db, "create_async_engine", fake_create)
    monkeypatch.setattr(settings, "wiki_database_url", SECRET_DSN)

    first = wiki_db.get_wiki_engine()
    second = wiki_db.get_wiki_engine()

    assert first is second
    assert len(created) == 1
    url, kwargs = created[0]
    assert url == SECRET_DSN
    # Лимит роли wiki_reader — 6 соединений, при пересоздании контейнера живут два пула
    assert kwargs["pool_size"] == 2
    assert kwargs["pool_size"] + kwargs["max_overflow"] <= 3
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_recycle"] > 0
    assert kwargs["pool_timeout"] > 0
    assert kwargs["connect_args"]["ssl"] == "require"
    assert kwargs["connect_args"]["timeout"] > 0
    assert kwargs["connect_args"]["command_timeout"] > 0

    await wiki_db.dispose_wiki_engine()
    assert first.disposed is True
    assert wiki_db._engine is None


async def test_dispose_without_engine_is_noop(reset_wiki_engine):
    await wiki_db.dispose_wiki_engine()
    assert wiki_db._engine is None


# --- Поиск: очистка запроса и параметры ---


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("грабли", "грабли:*"),
        ("  Грабли   HOME-page ", "грабли:* & home:* & page:*"),
        ("wiki_reader", "wiki:* & reader:*"),
        ("граб & !docker | (prune):* <-> x", "граб:* & docker:* & prune:* & x:*"),
        ("'); drop table notes; --", "drop:* & table:* & notes:*"),
        ("G112 5432", "g112:* & 5432:*"),
        ("ёлка\\ 'q' \"z\"", "ёлка:* & q:* & z:*"),
        ("", None),
        (None, None),
        (" :* & | ! ( ) <> ' \" \\ _ ", None),
    ],
)
def test_build_tsquery(raw, expected):
    assert wiki_service.build_tsquery(raw) == expected


def test_build_tsquery_limits_word_count():
    words = [f"w{i}" for i in range(wiki_service.MAX_SEARCH_WORDS + 5)]
    result = wiki_service.build_tsquery(" ".join(words))
    assert result is not None
    assert result.count(":*") == wiki_service.MAX_SEARCH_WORDS


async def test_search_notes_is_parameterized():
    """Ввод пользователя уходит только параметрами — в тексте SQL его нет."""
    conn = FakeConn()
    evil = "x'); drop table notes; --"

    await wiki_service.search_notes(conn, q=evil, project=evil, note_type=evil, tag=evil, limit=10)

    assert len(conn.calls) == 1
    sql, params = conn.calls[0]
    assert "drop table" not in sql
    assert "to_tsquery('simple', :tsquery)" in sql
    assert params == {
        "tsquery": "x:* & drop:* & table:* & notes:*",
        "project": evil,
        "note_type": evil,
        "tag": evil,
        "limit": 10,
    }


async def test_search_notes_filters_only():
    """Без слов в запросе — список по фильтрам, без to_tsquery."""
    conn = FakeConn()

    await wiki_service.search_notes(conn, q=" !! ", project=None, note_type="runbook", tag=None, limit=10)

    sql, params = conn.calls[0]
    assert "to_tsquery" not in sql
    assert params == {"note_type": "runbook", "limit": 10}


async def test_search_notes_without_conditions_skips_db():
    conn = FakeConn()

    assert await wiki_service.search_notes(conn, q=" :* ", project=None, note_type=None, tag=None, limit=10) == []
    assert conn.calls == []


async def test_summary_rows_are_normalized():
    """jsonb из сырого запроса приходит строкой, теги могут быть null."""
    row = {**SUMMARY, "metadata": '{"type": "journal"}', "tags": None}
    conn = FakeConn(results=[[row]])

    result = await wiki_service.get_recent_notes(conn, 5)

    assert result[0]["metadata"] == {"type": "journal"}
    assert result[0]["tags"] == []
    assert conn.calls[0][1] == {"limit": 5}


async def test_get_note_by_slug_collects_links():
    row = {
        "id": NOTE_ID,
        "slug": "a/b",
        "title": "T",
        "content": "C",
        "metadata": {"type": "reference"},
        "created_at": NOW,
        "updated_at": NOW,
        "notebook_id": None,
        "notebook_name": None,
        "notebook_slug": None,
        "tags": ["k8s"],
    }
    link = {"slug": "a/c", "title": "Цель", "alias": None}
    backlink = {"slug": "a/d", "title": "Источник", "alias": "псевдоним"}
    conn = FakeConn(results=[[row], [link], [backlink]])

    note = await wiki_service.get_note_by_slug(conn, "a/b")

    assert note["notebook"] is None
    assert note["links"] == [link]
    assert note["backlinks"] == [backlink]
    assert conn.calls[0][1] == {"slug": "a/b"}
    assert "backlinks_view" in conn.calls[2][0]
    assert conn.calls[1][1] == conn.calls[2][1] == {"note_id": NOTE_ID}


async def test_get_note_by_slug_missing():
    conn = FakeConn(results=[[]])
    assert await wiki_service.get_note_by_slug(conn, "net/takoi") is None
    assert len(conn.calls) == 1


async def test_get_notebook_notes_missing_notebook():
    conn = FakeConn(results=[[]])
    assert await wiki_service.get_notebook_notes(conn, NOTEBOOK_ID) is None
    assert len(conn.calls) == 1


def test_build_notebook_tree_counts_nested_notes():
    root, child, grandchild, orphan = (uuid.uuid4() for _ in range(4))
    rows = [
        {"id": root, "name": "Работа", "slug": "rabota", "parent_id": None, "note_count": 1},
        {"id": child, "name": "AnyFlow", "slug": "anyflow", "parent_id": root, "note_count": 10},
        {"id": grandchild, "name": "Зоны", "slug": "zony", "parent_id": child, "note_count": 5},
        # родителя нет в выборке — блокнот показывается корневым, а не теряется
        {"id": orphan, "name": "Разное", "slug": "raznoe", "parent_id": uuid.uuid4(), "note_count": 2},
    ]

    tree = wiki_service.build_notebook_tree(rows)

    assert [node["slug"] for node in tree] == ["rabota", "raznoe"]
    assert tree[0]["note_count"] == 1
    assert tree[0]["total_note_count"] == 16
    assert tree[0]["children"][0]["total_note_count"] == 15
    assert tree[0]["children"][0]["children"][0]["total_note_count"] == 5
    assert tree[1]["total_note_count"] == 2


# --- CORS ---


async def test_cors_preflight_from_wiki_origin(client: AsyncClient):
    origin = f"https://wiki.{settings.domain}"

    response = await client.options(
        "/api/wiki/notebooks",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"


async def test_cors_preflight_main_origin_still_allowed(client: AsyncClient):
    origin = f"https://{settings.domain}"

    response = await client.options(
        "/api/wiki/notebooks",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


async def test_cors_preflight_foreign_origin_rejected(client: AsyncClient):
    response = await client.options(
        "/api/wiki/notebooks",
        headers={"Origin": f"https://evil.{settings.domain}", "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


# --- Rate limit ---


@pytest.fixture
def enabled_limiter():
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.enabled = False
    limiter.reset()


async def test_wiki_limit_is_shared_and_skips_health(client: AsyncClient, enabled_limiter):
    """120/minute — один счётчик на IP для всех эндпоинтов вики; health в него не входит."""
    headers = {"X-Real-Ip": "203.0.113.40"}
    paths = ["/api/wiki/notebooks", "/api/wiki/recent", "/api/wiki/search?q=x", "/api/wiki/notes/a/b"]

    for i in range(120):
        response = await client.get(paths[i % len(paths)], headers=headers)
        assert response.status_code == 401, f"запрос {i + 1}: {response.status_code}"

    for path in paths:
        response = await client.get(path, headers=headers)
        assert response.status_code == 429

    # health не ограничен
    for _ in range(5):
        response = await client.get("/api/wiki/health", headers=headers)
        assert response.status_code == 200

    # другой IP не затронут
    response = await client.get("/api/wiki/notebooks", headers={"X-Real-Ip": "203.0.113.41"})
    assert response.status_code == 401


# --- Ошибка в самой строке подключения: тоже «недоступна», а не 500 ---

BROKEN_URLS = [
    # схема без +asyncpg — SQLAlchemy ищет другой драйвер (ModuleNotFoundError)
    "postgresql://wiki_reader.ref:s3cr3t%2Fpw@127.0.0.1:1/postgres",
    # нечисловой порт (ValueError)
    "postgresql+asyncpg://wiki_reader.ref:s3cr3t%2Fpw@127.0.0.1:abc/postgres",
    # параметр, которого asyncpg не знает (TypeError при подключении)
    "postgresql+asyncpg://wiki_reader.ref:s3cr3t%2Fpw@127.0.0.1:1/postgres?sslmode=require",
    # строка, которую не разобрать вовсе
    "s3cr3t%2Fpw-not-a-url",
]


@pytest.fixture(params=BROKEN_URLS)
def broken_wiki_url(request, monkeypatch, reset_wiki_engine) -> str:
    monkeypatch.setattr(settings, "wiki_database_url", request.param)
    return request.param


def _assert_no_secret_in_log(caplog, url: str) -> None:
    assert caplog.records, "сбой должен попасть в лог"
    for record in caplog.records:
        logged = record.getMessage() + (record.exc_text or "")
        if record.exc_info:
            logged += "".join(traceback.format_exception(*record.exc_info))
        assert url not in logged
        assert "s3cr3t" not in logged


async def test_broken_url_health_is_200_unavailable(client: AsyncClient, broken_wiki_url: str, caplog):
    with caplog.at_level(logging.DEBUG):
        response = await client.get("/api/wiki/health")

    assert response.status_code == 200
    assert response.json() == {"status": "unavailable"}
    assert "s3cr3t" not in response.text
    _assert_no_secret_in_log(caplog, broken_wiki_url)


async def test_broken_url_protected_returns_503(admin_client: AsyncClient, broken_wiki_url: str, caplog):
    for path in PROTECTED_PATHS:
        with caplog.at_level(logging.DEBUG):
            response = await admin_client.get(path)
        assert response.status_code == 503, f"{path}: {response.status_code}"
        assert response.json() == {"detail": "Wiki database is unavailable"}
    _assert_no_secret_in_log(caplog, broken_wiki_url)


def test_safe_error_text_hides_url_and_password(monkeypatch):
    url = "postgresql+asyncpg://wiki_reader.ref:p%40ss%2Fword@pooler.example:5432/postgres"
    monkeypatch.setattr(settings, "wiki_database_url", url)

    text_ = wiki_db._safe_error_text(ValueError(f"bad url {url}; password p%40ss%2Fword or p@ss/word"))

    assert text_.startswith("ValueError: ")
    assert url not in text_
    assert "p%40ss%2Fword" not in text_
    assert "p@ss/word" not in text_


async def test_endpoint_404_is_not_turned_into_503(admin_client: AsyncClient, wiki_data):
    """Исключение эндпоинта проходит через wiki_connection и должно остаться 404."""
    response = await admin_client.get("/api/wiki/notes/net/takoi")
    assert response.status_code == 404


# --- Нулевой байт во вводе: до базы не доходит ---


@pytest.mark.parametrize("param", ["project", "type", "tag"])
async def test_search_filter_with_nul_byte_is_422(admin_client: AsyncClient, wiki_engine: FakeEngine, param: str):
    response = await admin_client.get(f"/api/wiki/search?q=x&{param}=a%00b")

    assert response.status_code == 422
    assert wiki_engine.conn.calls == []


async def test_search_query_with_nul_byte_is_cleaned(admin_client: AsyncClient, wiki_engine: FakeEngine):
    """В q нулевой байт — просто разделитель слов."""
    response = await admin_client.get("/api/wiki/search?q=a%00b")

    assert response.status_code == 200
    assert wiki_engine.conn.calls[0][1]["tsquery"] == "a:* & b:*"


async def test_note_slug_with_nul_byte_is_404(admin_client: AsyncClient, wiki_engine: FakeEngine):
    response = await admin_client.get("/api/wiki/notes/a%00b")

    assert response.status_code == 404
    assert response.json() == {"detail": "Note not found"}
    assert wiki_engine.conn.calls == []
