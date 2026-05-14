"""Общие фикстуры для тестов бота."""
import json
import os
from pathlib import Path

import pytest

# Stub env для модулей, импортирующих app.main / app.config (pydantic Settings()
# валидирует обязательные поля при импорте). setdefault не перезатирает реальные значения.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("BOT_SECRET", "test-bot-secret")
os.environ.setdefault("CRON_SECRET", "test-cron-secret")
os.environ.setdefault("UPTIME_SECRET", "test-uptime-secret")

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def diary_sample() -> dict:
    """Образец ответа /student/getPrsDiary с тремя уроками: один с ДЗ, один без, один с оценкой."""
    return json.loads((FIXTURES / "eschool_diary_sample.json").read_text(encoding="utf-8"))
