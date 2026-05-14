"""Тесты для _alert_eschool_cookies_expired — алерт админам-Волковым о протухших cookies."""
from unittest.mock import AsyncMock

import pytest

from app import main


@pytest.fixture
def patched_alert(monkeypatch):
    """Изолирует _alert_eschool_cookies_expired от прода: подменяет mark_event_sent
    и api.get_eschool_admin_volkovs, возвращает (bot_mock, set_dedup_blocks, set_admins)."""
    bot = AsyncMock()

    dedup_blocks = {"value": False}

    def fake_mark_event_sent(key: str) -> bool:
        # True = ключ новый, отправляем; False = уже отправлено, пропускаем.
        return not dedup_blocks["value"]

    admins_holder = {"value": []}

    async def fake_get_admins():
        return admins_holder["value"]

    monkeypatch.setattr(main, "mark_event_sent", fake_mark_event_sent)
    monkeypatch.setattr(main.api, "get_eschool_admin_volkovs", fake_get_admins)

    def set_dedup_blocks(blocks: bool) -> None:
        dedup_blocks["value"] = blocks

    def set_admins(admins: list[dict]) -> None:
        admins_holder["value"] = admins

    return bot, set_dedup_blocks, set_admins


async def test_alert_sends_to_all_admins(patched_alert):
    bot, _, set_admins = patched_alert
    set_admins([{"tg_id": 111}, {"tg_id": 222}])

    await main._alert_eschool_cookies_expired(bot)

    assert bot.send_message.await_count == 2
    chat_ids = sorted(call.kwargs["chat_id"] for call in bot.send_message.await_args_list)
    assert chat_ids == [111, 222]


async def test_alert_text_includes_runbook_essentials(patched_alert):
    bot, _, set_admins = patched_alert
    set_admins([{"tg_id": 111}])

    await main._alert_eschool_cookies_expired(bot)

    text = bot.send_message.await_args.kwargs["text"]
    # Ключевые маркеры, по которым легко увидеть регрессию: основные команды для copy-paste
    # и название vault-переменной должны остаться в тексте, иначе админ не починит сессию.
    assert "cookies протухли" in text
    assert "check_eschool_cookies.py" in text
    assert "ansible-vault encrypt_string" in text
    assert "vault_eschool_cookies" in text
    assert "ansible-playbook" in text


async def test_alert_dedup_skips_when_already_sent(patched_alert):
    bot, set_dedup_blocks, set_admins = patched_alert
    set_admins([{"tg_id": 111}])
    set_dedup_blocks(True)  # mark_event_sent вернёт False — алерт уже был сегодня

    await main._alert_eschool_cookies_expired(bot)

    bot.send_message.assert_not_awaited()


async def test_alert_no_admins_does_not_crash(patched_alert):
    bot, _, set_admins = patched_alert
    set_admins([])  # ни одного админа-Волкова с tg_id

    await main._alert_eschool_cookies_expired(bot)

    bot.send_message.assert_not_awaited()


async def test_alert_continues_when_one_recipient_fails(patched_alert):
    """Если send_message для одного админа падает, остальные всё равно должны получить."""
    bot, _, set_admins = patched_alert
    set_admins([{"tg_id": 111}, {"tg_id": 222}])

    async def flaky_send(*, chat_id: int, text: str) -> None:
        if chat_id == 111:
            raise RuntimeError("telegram api down for this user")

    bot.send_message.side_effect = flaky_send

    await main._alert_eschool_cookies_expired(bot)

    # Обе попытки случились — _send_to_tg_ids ловит исключение и продолжает
    assert bot.send_message.await_count == 2
