"""Тесты для bot/app/eschool/service.py."""
from datetime import date

from app.eschool.service import next_school_day, week_range_ms


def test_next_school_day_monday_to_friday_returns_next_day():
    # 2026-05-11 — понедельник
    assert next_school_day(date(2026, 5, 11)) == date(2026, 5, 12)  # пн → вт
    assert next_school_day(date(2026, 5, 12)) == date(2026, 5, 13)  # вт → ср
    assert next_school_day(date(2026, 5, 13)) == date(2026, 5, 14)  # ср → чт
    assert next_school_day(date(2026, 5, 14)) == date(2026, 5, 15)  # чт → пт


def test_next_school_day_friday_returns_monday():
    # 2026-05-15 — пятница → понедельник 2026-05-18
    assert next_school_day(date(2026, 5, 15)) == date(2026, 5, 18)


def test_next_school_day_saturday_returns_monday():
    assert next_school_day(date(2026, 5, 16)) == date(2026, 5, 18)


def test_next_school_day_sunday_returns_monday():
    assert next_school_day(date(2026, 5, 17)) == date(2026, 5, 18)


def test_week_range_ms_returns_monday_00_to_sunday_2359():
    d1_ms, d2_ms = week_range_ms(date(2026, 5, 14))  # четверг
    diff_days = (d2_ms - d1_ms) / 1000 / 86400
    assert 6.9 < diff_days < 7.0
