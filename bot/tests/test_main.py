"""Тесты app.main: set_commands, run (с моками AppRunner/TCPSite/polling), main."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import api_client
from app import main as main_mod


def make_bot() -> MagicMock:
    bot = MagicMock()
    bot.set_my_commands = AsyncMock()
    bot.delete_webhook = AsyncMock()
    return bot


async def test_set_commands():
    bot = make_bot()

    await main_mod.set_commands(bot)

    bot.set_my_commands.assert_awaited_once()
    commands = bot.set_my_commands.await_args.args[0]
    assert [c.command for c in commands] == [
        "menu", "vote", "suggest", "recipes", "schedule", "mute", "unmute", "help",
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


async def test_run_cleans_up_on_polling_failure(web_mocks):
    runner, _ = web_mocks
    bot = make_bot()
    dp = MagicMock()
    dp.start_polling = AsyncMock(side_effect=RuntimeError("polling died"))

    with pytest.raises(RuntimeError):
        await main_mod.run(bot, dp)

    runner.cleanup.assert_awaited_once()
    api_client.api.close.assert_awaited_once()


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
    dp.include_router.assert_called_once_with(main_mod.main_router)
    assert len(run_calls) == 1
