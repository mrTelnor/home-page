"""Общие фикстуры для тестов бота."""
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def diary_sample() -> dict:
    """Образец ответа /student/getPrsDiary с тремя уроками: один с ДЗ, один без, один с оценкой."""
    return json.loads((FIXTURES / "eschool_diary_sample.json").read_text(encoding="utf-8"))
