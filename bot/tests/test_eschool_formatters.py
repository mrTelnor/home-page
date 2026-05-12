"""Тесты форматтеров сообщений eschool."""
from datetime import date

from app.eschool.formatters import (
    format_grades_digest,
    format_homework_digest,
    format_homework_push,
)
from app.eschool.models import Grade, HomeworkItem


def test_format_homework_digest_weekday_tomorrow():
    items = [
        HomeworkItem(lesson_id=1, variant_id=10, subject="Математика",
                     teacher="Иванова", text="№243 стр. 102", target_date=date(2026, 5, 13)),
        HomeworkItem(lesson_id=2, variant_id=11, subject="Русский",
                     teacher=None, text="упр. 188", target_date=date(2026, 5, 13)),
    ]
    text = format_homework_digest(items, today=date(2026, 5, 12), target_date=date(2026, 5, 13))
    assert "📚 <b>Домашка на завтра (среда, 13.05)</b>" in text
    assert "<b>Математика</b>" in text
    assert "  №243 стр. 102" in text
    assert "<b>Русский</b>" in text
    assert "  упр. 188" in text


def test_format_homework_digest_friday_for_monday():
    items = [
        HomeworkItem(lesson_id=1, variant_id=10, subject="Биология",
                     teacher="С.С.", text="параграф 12", target_date=date(2026, 5, 18)),
    ]
    text = format_homework_digest(items, today=date(2026, 5, 15), target_date=date(2026, 5, 18))
    assert "Домашка на понедельник" in text
    assert "(пн, 18.05)" in text


def test_format_homework_digest_saturday_says_napominaiu():
    items = [
        HomeworkItem(lesson_id=1, variant_id=10, subject="Биология",
                     teacher=None, text="параграф 12", target_date=date(2026, 5, 18)),
    ]
    text = format_homework_digest(items, today=date(2026, 5, 16), target_date=date(2026, 5, 18))
    assert "Напоминаю" in text
