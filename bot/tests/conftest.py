"""Общие фикстуры для тестов бота."""
import os

# Stub env для модулей, импортирующих app.main / app.config (pydantic Settings()
# валидирует обязательные поля при импорте). setdefault не перезатирает реальные значения.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("BOT_SECRET", "test-bot-secret")
os.environ.setdefault("CRON_SECRET", "test-cron-secret")
os.environ.setdefault("UPTIME_SECRET", "test-uptime-secret")
