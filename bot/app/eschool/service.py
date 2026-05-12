"""Бизнес-логика eschool: расчёт целевой даты, диапазона недели."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Moscow")


def next_school_day(today: date) -> date:
    """Возвращает дату следующего школьного дня.

    Пн–Чт → завтра. Пт → понедельник (+3). Сб → понедельник (+2). Вс → понедельник (+1).
    """
    weekday = today.weekday()  # 0=пн ... 6=вс
    if weekday <= 3:        # пн-чт
        return today + timedelta(days=1)
    if weekday == 4:        # пт
        return today + timedelta(days=3)
    if weekday == 5:        # сб
        return today + timedelta(days=2)
    return today + timedelta(days=1)  # вс


def week_range_ms(target: date) -> tuple[int, int]:
    """Возвращает (d1_ms, d2_ms) — границы недели, содержащей target, в миллисекундах UTC.

    d1 = понедельник 00:00:00 МСК, d2 = воскресенье 23:59:59 МСК.
    """
    monday = target - timedelta(days=target.weekday())
    sunday = monday + timedelta(days=6)
    d1 = datetime.combine(monday, time(0, 0, 0), tzinfo=TZ)
    d2 = datetime.combine(sunday, time(23, 59, 59), tzinfo=TZ)
    return int(d1.timestamp() * 1000), int(d2.timestamp() * 1000)
