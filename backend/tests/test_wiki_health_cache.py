"""Вики /api/wiki/health: кэш результата, одна проверка на одновременные запросы, записи в лог.

В Supabase тесты не ходят: engine базы знаний подменён заглушкой, которая считает
подключения. Время кэша подменяется (`wiki_db._monotonic`), без sleep.
"""
import asyncio
import logging

import pytest
from httpx import AsyncClient

from app.core import wiki_db
from tests.test_wiki import SECRET_DSN, FakeConn, FakeEngine, _db_error

HEALTH = "/api/wiki/health"


class FakeClock:
    """Часы кэша health: стоят на месте, пока тест их не сдвинет."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class CountingEngine(FakeEngine):
    """Заглушка engine: считает подключения, умеет «ломаться», «чиниться» и задерживать подключение."""

    def __init__(self, conn=None, connect_error=None, gate: asyncio.Event | None = None):
        super().__init__(conn=conn, connect_error=connect_error)
        self.connects = 0
        self.gate = gate

    def connect(self):
        engine = self

        class _Ctx:
            async def __aenter__(self):
                engine.connects += 1
                if engine.gate is not None:
                    await engine.gate.wait()
                if engine._connect_error is not None:
                    raise engine._connect_error
                return engine.conn

            async def __aexit__(self, *exc_info):
                return False

        return _Ctx()


@pytest.fixture
def clock(monkeypatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(wiki_db, "_monotonic", fake)
    return fake


def _use_engine(monkeypatch, engine: FakeEngine) -> FakeEngine:
    monkeypatch.setattr(wiki_db, "get_wiki_engine", lambda: engine)
    return engine


def _health_records(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == wiki_db.logger.name]


async def _status(client: AsyncClient) -> str:
    response = await client.get(HEALTH)
    assert response.status_code == 200
    assert set(response.json()) == {"status"}
    return response.json()["status"]


# --- Кэш ---


async def test_requests_within_window_hit_database_once(client: AsyncClient, monkeypatch, clock: FakeClock):
    engine = _use_engine(monkeypatch, CountingEngine())

    for _ in range(50):
        assert await _status(client) == "ok"
        clock.advance(wiki_db.WIKI_HEALTH_CACHE_TTL / 100)

    assert engine.connects == 1
    assert [sql.strip().lower() for sql, _ in engine.conn.calls] == ["select 1"]


async def test_cache_expires_after_ttl(client: AsyncClient, monkeypatch, clock: FakeClock):
    engine = _use_engine(monkeypatch, CountingEngine())

    assert await _status(client) == "ok"
    clock.advance(wiki_db.WIKI_HEALTH_CACHE_TTL - 0.001)
    assert await _status(client) == "ok"
    assert engine.connects == 1

    clock.advance(0.001)
    assert await _status(client) == "ok"
    assert engine.connects == 2


async def test_unavailable_is_cached_too(client: AsyncClient, monkeypatch, clock: FakeClock):
    """Недоступная база — тоже из кэша: поток запросов не стучится в неё и не ждёт таймаутов."""
    engine = _use_engine(monkeypatch, CountingEngine(connect_error=_db_error()))

    for _ in range(20):
        assert await _status(client) == "unavailable"

    assert engine.connects == 1


async def test_status_follows_database_after_window(client: AsyncClient, monkeypatch, clock: FakeClock):
    """В пределах окна — прежний статус, после окна — действительный."""
    engine = _use_engine(monkeypatch, CountingEngine())
    assert await _status(client) == "ok"

    engine._connect_error = _db_error()
    assert await _status(client) == "ok"
    clock.advance(wiki_db.WIKI_HEALTH_CACHE_TTL)
    assert await _status(client) == "unavailable"

    engine._connect_error = None
    assert await _status(client) == "unavailable"
    clock.advance(wiki_db.WIKI_HEALTH_CACHE_TTL)
    assert await _status(client) == "ok"
    assert engine.connects == 3


async def test_disabled_is_not_cached(client: AsyncClient, monkeypatch, clock: FakeClock):
    """«Выключена» в базу не ходит и в кэш не попадает: включённая вики видна сразу."""
    assert await _status(client) == "disabled"
    assert wiki_db._health_cache is None

    engine = _use_engine(monkeypatch, CountingEngine())
    assert await _status(client) == "ok"
    assert engine.connects == 1


async def test_cache_ttl_is_short():
    """Окно — секунды: smoke-тест деплоя и будильник Supabase не должны видеть давний статус."""
    assert 0 < wiki_db.WIKI_HEALTH_CACHE_TTL <= 60


# --- Одновременные запросы ---


async def test_concurrent_requests_share_one_check(client: AsyncClient, monkeypatch, clock: FakeClock):
    """Пустой кэш и 30 запросов разом: проверка одна, остальные ждут её результат."""
    gate = asyncio.Event()
    engine = _use_engine(monkeypatch, CountingEngine(gate=gate))

    requests = [asyncio.create_task(client.get(HEALTH)) for _ in range(30)]
    # Даём всем запросам дойти до ожидания проверки
    for _ in range(50):
        await asyncio.sleep(0)
    assert engine.connects == 1
    assert not any(task.done() for task in requests)

    gate.set()
    responses = await asyncio.gather(*requests)

    assert [r.status_code for r in responses] == [200] * 30
    assert [r.json() for r in responses] == [{"status": "ok"}] * 30
    assert engine.connects == 1
    assert len(engine.conn.calls) == 1


async def test_concurrent_requests_share_one_check_after_expiry(client: AsyncClient, monkeypatch, clock: FakeClock):
    """Истёкший кэш ведёт себя так же, как пустой."""
    engine = _use_engine(monkeypatch, CountingEngine())
    assert await _status(client) == "ok"

    clock.advance(wiki_db.WIKI_HEALTH_CACHE_TTL + 1)
    engine.gate = asyncio.Event()
    requests = [asyncio.create_task(client.get(HEALTH)) for _ in range(10)]
    for _ in range(50):
        await asyncio.sleep(0)
    assert engine.connects == 2

    engine.gate.set()
    responses = await asyncio.gather(*requests)

    assert [r.json() for r in responses] == [{"status": "ok"}] * 10
    assert engine.connects == 2


async def test_cancelled_waiter_does_not_break_check(monkeypatch, clock: FakeClock):
    """Отмена одного ждущего запроса не обрывает проверку для остальных."""
    gate = asyncio.Event()
    engine = _use_engine(monkeypatch, CountingEngine(gate=gate))

    first = asyncio.create_task(wiki_db.get_wiki_health())
    second = asyncio.create_task(wiki_db.get_wiki_health())
    for _ in range(10):
        await asyncio.sleep(0)

    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first

    gate.set()
    assert await second == "ok"
    assert engine.connects == 1
    # Результат проверки попал в кэш, след от неё не остался
    assert await wiki_db.get_wiki_health() == "ok"
    assert engine.connects == 1
    assert wiki_db._health_task is None


async def test_check_cancelled_before_start_does_not_stick(monkeypatch, clock: FakeClock):
    """Проверку отменили до её первого шага: следующий запрос запускает новую, а не получает отмену."""
    engine = _use_engine(monkeypatch, CountingEngine())

    # Задача создана так же, как в get_wiki_health, и отменена до первой прокрутки loop:
    # тело корутины не начиналось, её finally не выполнится
    check = asyncio.create_task(wiki_db._refresh_wiki_health())
    wiki_db._health_task = check
    check.cancel()
    with pytest.raises(asyncio.CancelledError):
        await check
    assert engine.connects == 0
    assert wiki_db._health_task is check

    for _ in range(3):
        assert await wiki_db.get_wiki_health() == "ok"
    assert engine.connects == 1
    assert wiki_db._health_task is None


# --- Лог ---


@pytest.mark.parametrize("failure", ["connect", "query"])
async def test_unavailable_is_logged_once_without_traceback(
    client: AsyncClient, monkeypatch, clock: FakeClock, caplog, failure: str
):
    """Серия запросов при недоступной базе — одна короткая запись, без трассировки и секретов."""
    if failure == "connect":
        engine = CountingEngine(connect_error=_db_error())
    else:
        engine = CountingEngine(conn=FakeConn(error=_db_error()))
    _use_engine(monkeypatch, engine)
    # Текст ошибки цитирует строку подключения — вычистить её можно, только зная настоящую
    monkeypatch.setattr(wiki_db.settings, "wiki_database_url", SECRET_DSN)
    caplog.set_level(logging.DEBUG)

    # Запросы идут дольше нескольких окон кэша: проверок несколько, запись одна
    for _ in range(40):
        assert await _status(client) == "unavailable"
        clock.advance(wiki_db.WIKI_HEALTH_CACHE_TTL / 10)

    assert engine.connects == 4
    records = _health_records(caplog)
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.ERROR
    assert record.exc_info is None
    assert record.exc_text is None
    message = record.getMessage()
    assert message.startswith("Wiki health check failed: OperationalError")
    assert "\n" not in message
    assert len(message) <= wiki_db.WIKI_HEALTH_ERROR_MAX_LENGTH + len("Wiki health check failed: ")
    assert "Traceback" not in caplog.text
    assert "s3cr3t" not in caplog.text


async def test_unavailable_log_repeats_not_more_often_than_interval(
    client: AsyncClient, monkeypatch, clock: FakeClock, caplog
):
    _use_engine(monkeypatch, CountingEngine(connect_error=_db_error()))
    caplog.set_level(logging.DEBUG)

    assert await _status(client) == "unavailable"
    clock.advance(wiki_db.WIKI_HEALTH_LOG_INTERVAL - 1)
    assert await _status(client) == "unavailable"
    assert len(_health_records(caplog)) == 1

    clock.advance(wiki_db.WIKI_HEALTH_CACHE_TTL)
    assert await _status(client) == "unavailable"
    assert len(_health_records(caplog)) == 2


async def test_recovery_is_logged_and_next_failure_is_logged_again(
    client: AsyncClient, monkeypatch, clock: FakeClock, caplog
):
    engine = _use_engine(monkeypatch, CountingEngine(connect_error=_db_error()))
    caplog.set_level(logging.DEBUG)

    assert await _status(client) == "unavailable"
    engine._connect_error = None
    clock.advance(wiki_db.WIKI_HEALTH_CACHE_TTL)
    assert await _status(client) == "ok"
    engine._connect_error = _db_error()
    clock.advance(wiki_db.WIKI_HEALTH_CACHE_TTL)
    assert await _status(client) == "unavailable"

    assert [r.levelno for r in _health_records(caplog)] == [logging.ERROR, logging.INFO, logging.ERROR]


async def test_ok_writes_nothing_to_log(client: AsyncClient, monkeypatch, clock: FakeClock, caplog):
    _use_engine(monkeypatch, CountingEngine())
    caplog.set_level(logging.DEBUG)

    for _ in range(5):
        assert await _status(client) == "ok"
        clock.advance(wiki_db.WIKI_HEALTH_CACHE_TTL)

    assert _health_records(caplog) == []


async def test_connection_string_in_error_is_not_logged(client: AsyncClient, monkeypatch, clock: FakeClock, caplog):
    """Ошибка цитирует строку подключения целиком — в запись health она не попадает."""
    monkeypatch.setattr(wiki_db.settings, "wiki_database_url", SECRET_DSN)
    _use_engine(monkeypatch, CountingEngine(connect_error=ValueError(f"bad url {SECRET_DSN}")))
    caplog.set_level(logging.DEBUG)

    assert await _status(client) == "unavailable"

    assert len(_health_records(caplog)) == 1
    assert SECRET_DSN not in caplog.text
    assert "s3cr3t" not in caplog.text


# --- Защищённые эндпоинты кэш не используют ---


async def test_protected_endpoint_ignores_cached_ok(admin_client: AsyncClient, monkeypatch, clock: FakeClock):
    """В кэше health «ok», а база уже упала: защищённый эндпоинт идёт в базу и отдаёт 503."""
    engine = _use_engine(monkeypatch, CountingEngine())
    assert await _status(admin_client) == "ok"

    engine._connect_error = _db_error()
    response = await admin_client.get("/api/wiki/recent")

    assert response.status_code == 503
    assert response.json() == {"detail": "Wiki database is unavailable"}
    assert engine.connects == 2
    assert await _status(admin_client) == "ok"


async def test_protected_endpoint_ignores_cached_unavailable(
    admin_client: AsyncClient, monkeypatch, clock: FakeClock
):
    """В кэше health «unavailable», а база уже поднялась: защищённый эндпоинт работает."""
    engine = _use_engine(monkeypatch, CountingEngine(connect_error=_db_error()))
    assert await _status(admin_client) == "unavailable"

    engine._connect_error = None
    response = await admin_client.get("/api/wiki/recent")

    assert response.status_code == 200
    assert engine.connects == 2
    assert await _status(admin_client) == "unavailable"


async def test_protected_endpoint_failure_still_logs_traceback(
    admin_client: AsyncClient, monkeypatch, clock: FakeClock, caplog
):
    """Журналирование защищённых эндпоинтов не изменилось: сбой запроса — с трассировкой."""
    _use_engine(monkeypatch, CountingEngine(conn=FakeConn(error=_db_error())))
    caplog.set_level(logging.DEBUG)

    response = await admin_client.get("/api/wiki/recent")

    assert response.status_code == 503
    records = _health_records(caplog)
    assert [r.getMessage() for r in records] == ["Wiki database request failed"]
    assert records[0].exc_info is not None
