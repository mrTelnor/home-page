"""Вики /api/wiki/health: дополнительные проверки QA к test_wiki_health_cache.py.

Отмена запросов, неожиданные сбои проверки, остановка приложения во время проверки,
чистка секретов до обрезки текста, настоящий пул SQLAlchemy. В Supabase тесты не ходят:
заглушка engine, настоящий engine к тестовой базе либо к закрытому порту 127.0.0.1.
Время кэша подменяется (`wiki_db._monotonic`), без sleep.
"""
import asyncio
import gc
import logging

import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine

from app.core import wiki_db
from app.core.config import settings
from app.core.ratelimit import limiter
from tests.test_wiki import SECRET_DSN, FakeConn, _db_error
from tests.test_wiki_health_cache import HEALTH, CountingEngine, FakeClock, _health_records, _status, _use_engine
from tests.test_wiki_qa import DB_PASSWORD, UNREACHABLE_DSN

PREFIX = "Wiki health check failed: "


@pytest.fixture
def clock(monkeypatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(wiki_db, "_monotonic", fake)
    return fake


async def _spin(times: int = 20) -> None:
    """Дать event loop прокрутить уже запущенные задачи (это не ожидание по времени)."""
    for _ in range(times):
        await asyncio.sleep(0)


# --- Отмена запросов ---


async def test_cancelled_creator_does_not_lose_check(monkeypatch, clock: FakeClock):
    """Отменён запрос, который запустил проверку, других ждущих нет: проверка доходит до конца."""
    gate = asyncio.Event()
    engine = _use_engine(monkeypatch, CountingEngine(gate=gate))

    creator = asyncio.create_task(wiki_db.get_wiki_health())
    await _spin()
    assert engine.connects == 1
    creator.cancel()
    with pytest.raises(asyncio.CancelledError):
        await creator

    # Проверка ещё идёт: новый запрос присоединяется к ней, а не запускает вторую
    late = asyncio.create_task(wiki_db.get_wiki_health())
    await _spin()
    assert engine.connects == 1

    gate.set()
    assert await late == "ok"
    assert wiki_db._health_task is None
    assert await wiki_db.get_wiki_health() == "ok"
    assert engine.connects == 1


async def test_all_waiters_cancelled_failed_check_is_cached_quietly(monkeypatch, clock: FakeClock, caplog):
    """Все ждущие отменены, проверка упала: результат в кэше, «невостребованных» исключений нет."""
    gate = asyncio.Event()
    engine = _use_engine(monkeypatch, CountingEngine(connect_error=_db_error(), gate=gate))
    caplog.set_level(logging.DEBUG)

    waiters = [asyncio.create_task(wiki_db.get_wiki_health()) for _ in range(5)]
    await _spin()
    for waiter in waiters:
        waiter.cancel()
    await asyncio.gather(*waiters, return_exceptions=True)

    gate.set()
    await _spin()
    gc.collect()

    assert wiki_db._health_task is None
    assert await wiki_db.get_wiki_health() == "unavailable"
    assert engine.connects == 1
    assert [r for r in caplog.records if r.name == "asyncio"] == []
    assert len(_health_records(caplog)) == 1


async def test_cancelled_check_does_not_stick(monkeypatch, clock: FakeClock):
    """Отменена сама проверка (остановка приложения): следующий запрос запускает новую."""
    gate = asyncio.Event()
    engine = _use_engine(monkeypatch, CountingEngine(gate=gate))

    waiter = asyncio.create_task(wiki_db.get_wiki_health())
    await _spin()
    wiki_db._health_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter

    assert wiki_db._health_task is None
    assert wiki_db._health_cache is None
    gate.set()
    assert await wiki_db.get_wiki_health() == "ok"
    assert engine.connects == 2


# --- Неожиданные сбои проверки ---


@pytest.mark.parametrize("error", [RuntimeError("boom"), KeyError("x"), AssertionError("y"), TimeoutError()])
@pytest.mark.parametrize("failure", ["connect", "query"])
async def test_unexpected_error_is_unavailable_and_cache_recovers(
    client: AsyncClient, monkeypatch, clock: FakeClock, failure: str, error: Exception
):
    """Исключение не из списка ошибок БД: health всё равно 200, после окна статус действительный."""
    if failure == "connect":
        engine = CountingEngine(connect_error=error)
    else:
        engine = CountingEngine(conn=FakeConn(error=error))
    _use_engine(monkeypatch, engine)

    assert await _status(client) == "unavailable"
    assert await _status(client) == "unavailable"
    assert engine.connects == 1
    assert wiki_db._health_task is None

    engine._connect_error = None
    engine.conn = FakeConn()
    clock.advance(wiki_db.WIKI_HEALTH_CACHE_TTL)
    assert await _status(client) == "ok"


async def test_get_engine_failure_is_unavailable(client: AsyncClient, monkeypatch, clock: FakeClock, caplog):
    """Сбой ещё при создании engine (кривая строка подключения) — тоже «недоступна», без секрета в логе."""
    monkeypatch.setattr(wiki_db.settings, "wiki_database_url", SECRET_DSN)

    def broken():
        raise ValueError(f"Could not parse URL {SECRET_DSN}")

    monkeypatch.setattr(wiki_db, "get_wiki_engine", broken)
    caplog.set_level(logging.DEBUG)

    assert await _status(client) == "unavailable"
    assert await _status(client) == "unavailable"

    assert len(_health_records(caplog)) == 1
    assert "s3cr3t" not in caplog.text


async def test_crashed_check_does_not_stick(monkeypatch, clock: FakeClock):
    """Даже если проверка упадёт исключением наружу, следующий запрос запускает новую, а не получает старую ошибку."""
    calls = 0

    async def probe():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("boom")
        return "ok", None

    monkeypatch.setattr(wiki_db, "_probe_wiki", probe)

    with pytest.raises(RuntimeError):
        await wiki_db.get_wiki_health()
    assert wiki_db._health_task is None
    assert wiki_db._health_cache is None

    assert await wiki_db.get_wiki_health() == "ok"
    assert calls == 2


# --- Окно кэша ---


async def test_window_counts_from_end_of_slow_check(monkeypatch, clock: FakeClock):
    """Проверка шла дольше окна (таймаут): результат всё равно живёт полное окно после её конца."""
    gate = asyncio.Event()
    engine = _use_engine(monkeypatch, CountingEngine(connect_error=_db_error(), gate=gate))

    waiter = asyncio.create_task(wiki_db.get_wiki_health())
    await _spin()
    clock.advance(wiki_db.WIKI_HEALTH_CACHE_TTL * 2)
    gate.set()
    assert await waiter == "unavailable"

    clock.advance(wiki_db.WIKI_HEALTH_CACHE_TTL - 0.001)
    assert await wiki_db.get_wiki_health() == "unavailable"
    assert engine.connects == 1


async def test_requests_during_slow_check_do_not_start_second_one(client: AsyncClient, monkeypatch, clock: FakeClock):
    """Пока проверка идёт, время уходит за окно, запросы приходят волнами — проверка одна."""
    gate = asyncio.Event()
    engine = _use_engine(monkeypatch, CountingEngine(gate=gate))

    requests = []
    for _ in range(5):
        requests += [asyncio.create_task(client.get(HEALTH)) for _ in range(10)]
        await _spin(50)
        clock.advance(wiki_db.WIKI_HEALTH_CACHE_TTL)
    assert engine.connects == 1

    gate.set()
    responses = await asyncio.gather(*requests)
    assert [r.json() for r in responses] == [{"status": "ok"}] * 50
    assert engine.connects == 1


# --- Лог ---


async def test_concurrent_requests_on_failure_log_once(client: AsyncClient, monkeypatch, clock: FakeClock, caplog):
    gate = asyncio.Event()
    engine = _use_engine(monkeypatch, CountingEngine(connect_error=_db_error(), gate=gate))
    monkeypatch.setattr(wiki_db.settings, "wiki_database_url", SECRET_DSN)
    caplog.set_level(logging.DEBUG)

    requests = [asyncio.create_task(client.get(HEALTH)) for _ in range(30)]
    await _spin(50)
    gate.set()
    responses = await asyncio.gather(*requests)

    assert [r.json() for r in responses] == [{"status": "unavailable"}] * 30
    assert engine.connects == 1
    assert len(_health_records(caplog)) == 1


@pytest.mark.parametrize("padding", range(240, 300, 3))
async def test_secret_is_cleaned_before_truncation(monkeypatch, clock: FakeClock, caplog, padding: int):
    """Строка подключения попадает на границу обрезки: в логе нет ни её, ни куска пароля."""
    monkeypatch.setattr(wiki_db.settings, "wiki_database_url", SECRET_DSN)
    _use_engine(monkeypatch, CountingEngine(connect_error=ValueError("x" * padding + SECRET_DSN + " tail")))
    caplog.set_level(logging.DEBUG)

    assert await wiki_db.get_wiki_health() == "unavailable"

    message = _health_records(caplog)[0].getMessage()
    assert len(message) <= len(PREFIX) + wiki_db.WIKI_HEALTH_ERROR_MAX_LENGTH
    # Ни пароля, ни его начала, ни начала строки подключения с именем роли
    for fragment in ("s3cr3t", "s3c", "wiki_reader", "pooler.example"):
        assert fragment not in message


async def test_password_alone_and_percent_encoded_is_cleaned(monkeypatch, clock: FakeClock, caplog):
    """Драйвер цитирует не строку целиком, а только пароль — в закодированном и раскодированном виде."""
    url = "postgresql+asyncpg://wiki_reader.ref:p%40ss%2Fw0rd@pooler.example:5432/postgres"
    monkeypatch.setattr(wiki_db.settings, "wiki_database_url", url)
    error = RuntimeError("auth failed, password 'p@ss/w0rd' (raw p%40ss%2Fw0rd)")
    _use_engine(monkeypatch, CountingEngine(connect_error=error))
    caplog.set_level(logging.DEBUG)

    assert await wiki_db.get_wiki_health() == "unavailable"

    message = _health_records(caplog)[0].getMessage()
    assert "p@ss/w0rd" not in message
    assert "p%40ss%2Fw0rd" not in message


async def test_long_outage_log_rate(client: AsyncClient, monkeypatch, clock: FakeClock, caplog):
    """Час недоступности под потоком запросов: записей — по одной на интервал, а не на проверку."""
    engine = _use_engine(monkeypatch, CountingEngine(connect_error=_db_error()))
    caplog.set_level(logging.DEBUG)

    steps = 3600 // wiki_db.WIKI_HEALTH_CACHE_TTL
    for _ in range(steps):
        assert await _status(client) == "unavailable"
        clock.advance(wiki_db.WIKI_HEALTH_CACHE_TTL)

    assert engine.connects == steps
    records = _health_records(caplog)
    assert len(records) == 3600 // wiki_db.WIKI_HEALTH_LOG_INTERVAL
    assert {r.levelno for r in records} == {logging.ERROR}


async def test_new_failure_right_after_recovery_is_not_muted_by_interval(
    client: AsyncClient, monkeypatch, clock: FakeClock, caplog
):
    """Долгий сбой, восстановление и новый сбой внутри интервала повтора: новая запись появляется сразу."""
    engine = _use_engine(monkeypatch, CountingEngine(connect_error=_db_error()))
    caplog.set_level(logging.DEBUG)

    assert await _status(client) == "unavailable"
    # Вторая запись о том же сбое — и сразу после неё восстановление
    clock.advance(wiki_db.WIKI_HEALTH_LOG_INTERVAL)
    assert await _status(client) == "unavailable"
    engine._connect_error = None
    clock.advance(wiki_db.WIKI_HEALTH_CACHE_TTL)
    assert await _status(client) == "ok"
    engine._connect_error = _db_error()
    clock.advance(wiki_db.WIKI_HEALTH_CACHE_TTL)
    assert await _status(client) == "unavailable"

    levels = [r.levelno for r in _health_records(caplog)]
    assert levels == [logging.ERROR, logging.ERROR, logging.INFO, logging.ERROR]


async def test_disabled_writes_nothing_and_does_not_touch_engine(client: AsyncClient, clock: FakeClock, caplog):
    caplog.set_level(logging.DEBUG)

    for _ in range(20):
        assert await _status(client) == "disabled"

    assert _health_records(caplog) == []
    assert wiki_db._engine is None
    assert wiki_db._health_task is None
    assert wiki_db._health_cache is None


# --- Контракт ---


async def test_health_burst_is_public_unlimited_and_hits_database_once(
    client: AsyncClient, monkeypatch, clock: FakeClock
):
    """Поток анонимных запросов с включённым лимитером: все 200, обращение к базе одно."""
    engine = _use_engine(monkeypatch, CountingEngine())
    limiter.enabled = True
    limiter.reset()
    try:
        responses = [await client.get(HEALTH, headers={"X-Real-Ip": "203.0.113.77"}) for _ in range(300)]
    finally:
        limiter.enabled = False
        limiter.reset()

    assert {r.status_code for r in responses} == {200}
    assert {r.text for r in responses} == {'{"status":"ok"}'}
    assert engine.connects == 1


# --- Настоящий пул SQLAlchemy ---


async def test_real_pool_concurrent_health_uses_one_connection(client: AsyncClient, monkeypatch, clock: FakeClock):
    """Настоящий engine (тестовая база) с пулом как у вики: 40 запросов разом — одно соединение, пул свободен."""
    engine = create_async_engine(
        settings.database_url, pool_size=wiki_db.WIKI_POOL_SIZE, max_overflow=wiki_db.WIKI_MAX_OVERFLOW
    )
    checkouts: list[int] = []
    event.listen(engine.sync_engine, "checkout", lambda *args: checkouts.append(engine.pool.checkedout()))
    monkeypatch.setattr(wiki_db, "get_wiki_engine", lambda: engine)
    try:
        responses = await asyncio.gather(*[client.get(HEALTH) for _ in range(40)])
        assert [r.json() for r in responses] == [{"status": "ok"}] * 40
        assert len(checkouts) == 1
        assert engine.pool.checkedout() == 0

        clock.advance(wiki_db.WIKI_HEALTH_CACHE_TTL)
        responses = await asyncio.gather(*[client.get(HEALTH) for _ in range(40)])
        assert [r.json() for r in responses] == [{"status": "ok"}] * 40
        assert len(checkouts) == 2
        assert max(checkouts) == 1
        assert engine.pool.checkedout() == 0
    finally:
        await engine.dispose()


async def test_real_engine_unreachable_series_logs_one_short_line(client: AsyncClient, monkeypatch, clock, caplog):
    """Настоящий engine вики, порт закрыт: серия запросов — одна строка без трассировки и пароля."""
    monkeypatch.setattr(wiki_db, "_engine", None)
    monkeypatch.setattr(settings, "wiki_database_url", UNREACHABLE_DSN)
    caplog.set_level(logging.DEBUG)
    try:
        for _ in range(15):
            assert await _status(client) == "unavailable"
        pool = wiki_db.get_wiki_engine().pool
        assert pool.checkedout() == 0
    finally:
        await wiki_db.dispose_wiki_engine()

    records = _health_records(caplog)
    assert len(records) == 1
    assert records[0].exc_info is None
    assert records[0].getMessage().startswith(PREFIX)
    assert "\n" not in records[0].getMessage()
    assert DB_PASSWORD not in caplog.text
    assert UNREACHABLE_DSN not in caplog.text
    assert "Traceback" not in caplog.text


# --- Остановка приложения и смена event loop ---


def _run_like_uvicorn(main) -> list[dict]:
    """Выполнить корутину в отдельном loop и закрыть его, как asyncio.run: отменить остаток задач.

    Возвращает всё, что дошло до обработчика исключений loop («Task was destroyed but it is
    pending», «exception was never retrieved»).
    """
    problems: list[dict] = []
    loop = asyncio.new_event_loop()
    loop.set_exception_handler(lambda _loop, context: problems.append(context))
    try:
        loop.run_until_complete(main())
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()

        async def drain():
            await asyncio.gather(*pending, return_exceptions=True)

        loop.run_until_complete(drain())
        loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        loop.close()
    gc.collect()
    return problems


def test_dispose_during_running_check_is_clean(monkeypatch, recwarn):
    """Приложение останавливается, пока проверка ждёт базу: ни исключений, ни брошенных задач."""
    engine = CountingEngine()
    monkeypatch.setattr(wiki_db, "get_wiki_engine", lambda: engine)
    monkeypatch.setattr(wiki_db, "_engine", engine)

    async def main():
        engine.gate = asyncio.Event()
        request = asyncio.create_task(wiki_db.get_wiki_health())
        await _spin()
        assert engine.connects == 1
        await wiki_db.dispose_wiki_engine()
        assert engine.disposed is True
        request.cancel()

    problems = _run_like_uvicorn(main)

    assert problems == []
    assert [str(w.message) for w in recwarn.list if "never awaited" in str(w.message)] == []
    assert wiki_db._health_task is None
    # Проверка, оборванная остановкой, результат не записала
    assert wiki_db._health_cache is None


def test_check_finishing_after_dispose_does_not_raise(monkeypatch):
    """Проверка успела закончиться уже после dispose: исключений нет, ждущий запрос получает статус."""
    engine = CountingEngine()
    monkeypatch.setattr(wiki_db, "get_wiki_engine", lambda: engine)
    monkeypatch.setattr(wiki_db, "_engine", engine)
    result: list[str] = []

    async def main():
        engine.gate = asyncio.Event()
        request = asyncio.create_task(wiki_db.get_wiki_health())
        await _spin()
        await wiki_db.dispose_wiki_engine()
        engine.gate.set()
        result.append(await request)

    problems = _run_like_uvicorn(main)

    assert problems == []
    assert result == ["ok"]
    assert wiki_db._health_task is None


def test_state_does_not_leak_between_event_loops(monkeypatch):
    """Loop закрылся с идущей проверкой (без сброса кэша): в новом loop health работает."""
    engine = CountingEngine()
    monkeypatch.setattr(wiki_db, "get_wiki_engine", lambda: engine)
    result: list[str] = []

    async def first():
        engine.gate = asyncio.Event()
        asyncio.create_task(wiki_db.get_wiki_health())
        await _spin()
        assert wiki_db._health_task is not None

    async def second():
        engine.gate = None
        result.append(await wiki_db.get_wiki_health())

    assert _run_like_uvicorn(first) == []
    assert wiki_db._health_task is None
    assert _run_like_uvicorn(second) == []

    assert result == ["ok"]
    assert engine.connects == 2
