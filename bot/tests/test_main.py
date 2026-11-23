"""Тесты app.main: set_commands, run (с моками AppRunner/TCPSite/polling), main."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import api_client
from app import main as main_mod


def make_bot() -> MagicMock:
    bot = MagicMock()
    bot.set_my_commands = AsyncMock()
    bot.delete_webhook = AsyncMock()
    bot.session.close = AsyncMock()
    return bot


async def test_set_commands():
    bot = make_bot()

    await main_mod.set_commands(bot)

    bot.set_my_commands.assert_awaited_once()
    commands = bot.set_my_commands.await_args.args[0]
    assert [c.command for c in commands] == [
        "menu", "vote", "suggest", "recipes", "schedule", "notifications", "mute", "unmute", "help",
    ]
    assert all(c.description for c in commands)


@pytest.fixture
def web_mocks(monkeypatch):
    runner = MagicMock()
    runner.setup = AsyncMock()
    runner.cleanup = AsyncMock()
    site = MagicMock()
    site.start = AsyncMock()
    monkeypatch.setattr(main_mod.web, "AppRunner", MagicMock(return_value=runner))
    monkeypatch.setattr(main_mod.web, "TCPSite", MagicMock(return_value=site))
    monkeypatch.setattr(api_client.api, "close", AsyncMock())
    return runner, site


async def test_run_starts_server_and_polling(web_mocks):
    runner, site = web_mocks
    bot = make_bot()
    dp = MagicMock()
    dp.start_polling = AsyncMock()

    await main_mod.run(bot, dp)

    runner.setup.assert_awaited_once()
    site.start.assert_awaited_once()
    bot.delete_webhook.assert_awaited_once_with(drop_pending_updates=True)
    bot.set_my_commands.assert_awaited_once()
    dp.start_polling.assert_awaited_once_with(bot)
    runner.cleanup.assert_awaited_once()
    api_client.api.close.assert_awaited_once()
    bot.session.close.assert_awaited_once()


async def test_run_cleans_up_on_polling_failure(web_mocks):
    runner, _ = web_mocks
    bot = make_bot()
    dp = MagicMock()
    dp.start_polling = AsyncMock(side_effect=RuntimeError("polling died"))

    with pytest.raises(RuntimeError, match="polling died"):
        await main_mod.run(bot, dp)

    runner.cleanup.assert_awaited_once()
    api_client.api.close.assert_awaited_once()
    bot.session.close.assert_awaited_once()


async def test_run_cleans_up_on_startup_failure(web_mocks):
    runner, _ = web_mocks
    bot = make_bot()
    bot.delete_webhook = AsyncMock(side_effect=RuntimeError("startup died"))
    dp = MagicMock()
    dp.start_polling = AsyncMock()

    with pytest.raises(RuntimeError, match="startup died"):
        await main_mod.run(bot, dp)

    dp.start_polling.assert_not_awaited()
    runner.cleanup.assert_awaited_once()
    api_client.api.close.assert_awaited_once()
    bot.session.close.assert_awaited_once()


async def test_run_cleanup_does_not_stop_after_runner_failure(web_mocks):
    runner, _ = web_mocks
    runner.cleanup = AsyncMock(side_effect=RuntimeError("runner cleanup died"))
    bot = make_bot()
    dp = MagicMock()
    dp.start_polling = AsyncMock()

    with pytest.raises(RuntimeError, match="runner cleanup died"):
        await main_mod.run(bot, dp)

    api_client.api.close.assert_awaited_once()
    bot.session.close.assert_awaited_once()


def test_main_wires_bot_and_dispatcher(monkeypatch):
    bot = make_bot()
    bot_cls = MagicMock(return_value=bot)
    monkeypatch.setattr(main_mod, "Bot", bot_cls)
    dp = MagicMock()
    monkeypatch.setattr(main_mod, "Dispatcher", MagicMock(return_value=dp))
    run_calls = []

    def fake_asyncio_run(coro):
        run_calls.append(coro)
        coro.close()

    monkeypatch.setattr(main_mod.asyncio, "run", fake_asyncio_run)

    main_mod.main()

    bot_cls.assert_called_once()
    assert bot_cls.call_args.kwargs["session"] is None
    dp.include_router.assert_called_once_with(main_mod.main_router)
    assert len(run_calls) == 1


def test_main_uses_relay_session_when_configured(monkeypatch):
    monkeypatch.setattr(main_mod.settings, "telegram_relay_url", "https://relay.example.test")
    monkeypatch.setattr(main_mod.settings, "telegram_relay_key", "test-relay-key")
    bot = make_bot()
    bot_cls = MagicMock(return_value=bot)
    monkeypatch.setattr(main_mod, "Bot", bot_cls)
    relay_session = MagicMock()
    relay_session_cls = MagicMock(return_value=relay_session)
    monkeypatch.setattr(main_mod, "TelegramRelaySession", relay_session_cls)
    dp = MagicMock()
    monkeypatch.setattr(main_mod, "Dispatcher", MagicMock(return_value=dp))

    def fake_asyncio_run(coro):
        coro.close()

    monkeypatch.setattr(main_mod.asyncio, "run", fake_asyncio_run)

    main_mod.main()

    relay_session_cls.assert_called_once_with(
        relay_url="https://relay.example.test",
        relay_key="test-relay-key",
    )
    assert bot_cls.call_args.kwargs["session"] is relay_session
