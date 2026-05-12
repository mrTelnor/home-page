"""Форматирование сообщений eschool для Telegram (HTML parse mode)."""
from __future__ import annotations

from datetime import date

from app.eschool.models import Grade, HomeworkItem

WEEKDAYS_RU = ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье")
WEEKDAYS_SHORT_RU = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")


def _digest_header(today: date, target_date: date) -> str:
    target_weekday = WEEKDAYS_SHORT_RU[target_date.weekday()]
    target_str = f"{target_weekday}, {target_date.strftime('%d.%m')}"
    today_weekday = today.weekday()

    if today_weekday <= 3:
        # пн-чт → "на завтра (<weekday>, ДД.ММ)"
        tomorrow_full = WEEKDAYS_RU[target_date.weekday()]
        return f"📚 <b>Домашка на завтра ({tomorrow_full}, {target_date.strftime('%d.%m')})</b>"
    if today_weekday == 4:
        # пт → "на понедельник"
        return f"📚 <b>Домашка на понедельник ({target_str})</b>"
    # сб, вс → "Напоминаю — на понедельник"
    return f"📚 <b>Напоминаю — домашка на понедельник ({target_str})</b>"


def _items_block(items: list[HomeworkItem]) -> str:
    # Группируем по subject (сохраняя порядок появления)
    by_subject: dict[str, list[HomeworkItem]] = {}
    for item in items:
        by_subject.setdefault(item.subject, []).append(item)

    lines: list[str] = []
    for subject, group in by_subject.items():
        lines.append(f"<b>{subject}</b>")
        for it in group:
            lines.append(f"  {it.text}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_homework_digest(items: list[HomeworkItem], today: date, target_date: date) -> str:
    """Дайджест ДЗ на target_date. items могут быть пустыми — функция не предполагает это.
    Вызывающий должен сам решить, отправлять ли пустое."""
    header = _digest_header(today, target_date)
    body = _items_block(items)
    return f"{header}\n\n{body}"


def format_homework_push(items: list[HomeworkItem], target_date: date) -> str:
    """Push новых ДЗ — кратко и без эмодзи-шапки про 'завтра'."""
    date_str = target_date.strftime("%d.%m")
    header = f"📝 <b>Новое домашнее задание на {date_str}</b>"
    body = _items_block(items)
    return f"{header}\n\n{body}"


def format_grades_digest(grades: list[Grade], target_date: date) -> str:
    """Дайджест оценок за target_date. Объединяет несколько оценок по одному предмету."""
    date_str = target_date.strftime("%d.%m")
    header = f"📊 <b>Оценки за сегодня ({date_str})</b>"

    # Группируем оценки по предмету (сохраняя порядок появления)
    by_subject: dict[str, list[Grade]] = {}
    for g in grades:
        by_subject.setdefault(g.subject, []).append(g)

    lines: list[str] = []
    for subject, group in by_subject.items():
        # Если у группы из одной оценки есть comment — добавляем его в строку
        if len(group) == 1 and group[0].comment:
            lines.append(f"<b>{subject}:</b> {group[0].value} — {group[0].comment}")
        else:
            values = ", ".join(g.value for g in group)
            lines.append(f"<b>{subject}:</b> {values}")
    body = "\n".join(lines)
    return f"{header}\n\n{body}"
