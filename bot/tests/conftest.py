"""Общие фикстуры для тестов бота."""
import os

# Stub env для модулей, импортирующих app.main / app.config (pydantic Settings()
# валидирует обязательные поля при импорте). setdefault не перезатирает реальные значения.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("BOT_SECRET", "test-bot-secret")
os.environ.setdefault("CRON_SECRET", "test-cron-secret")
os.environ.setdefault("UPTIME_SECRET", "test-uptime-secret")

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_reminders_state(tmp_path, monkeypatch):
    """Файл дедупа — во временный каталог: иначе тесты писали бы в /data/sent_reminders.json."""
    from app.config import settings

    monkeypatch.setattr(settings, "reminders_data_path", str(tmp_path / "sent_reminders.json"))
