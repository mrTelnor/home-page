"""Парсер ответов eschool API."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from app.eschool.models import Grade, HomeworkItem

TZ = ZoneInfo("Europe/Moscow")


def _lesson_date(lesson: dict) -> date:
    """Дата урока в МСК.

    Сначала пробуем `date_d` (формат YYYY-MM-DD), иначе конвертируем
    миллисекундный `date` через TZ.
    """
    date_d = lesson.get("date_d")
    if date_d:
        return date.fromisoformat(date_d)
    return datetime.fromtimestamp(lesson["date"] / 1000, tz=TZ).date()


def _extract_text(variant: dict) -> str:
    """Возвращает чистый текст ДЗ: preview если есть и непустой, иначе strip(HTML)."""
    preview = (variant.get("preview") or "").strip()
    if preview:
        return preview
    html = variant.get("text", "") or ""
    return BeautifulSoup(html, "html.parser").get_text().strip()


def _lesson_matches_date(lesson: dict, target_date: date) -> bool:
    """Возвращает True, если урок прошёл в `target_date` (с защитой от плохих данных)."""
    try:
        return _lesson_date(lesson) == target_date
    except (KeyError, ValueError):
        return False


def _homework_from_lesson(lesson: dict, target_date: date) -> list[HomeworkItem]:
    """Собирает все ДЗ-варианты для одного урока."""
    subject = (lesson.get("unit") or {}).get("name") or "Без названия"
    teacher = (lesson.get("teacher") or {}).get("factTeacherIN")
    lesson_id = lesson.get("id")

    result: list[HomeworkItem] = []
    for part in lesson.get("part", []) or []:
        if part.get("cat") != "DZ" or not part.get("hasTask"):
            continue
        for variant in part.get("variant", []) or []:
            text = _extract_text(variant)
            if not text:
                continue
            result.append(HomeworkItem(
                lesson_id=lesson_id,
                variant_id=variant.get("id"),
                subject=subject,
                teacher=teacher,
                text=text,
                target_date=target_date,
            ))
    return result


def parse_homework(diary: dict, target_date: date) -> list[HomeworkItem]:
    """Извлекает все ДЗ-задания на `target_date` из ответа getPrsDiary."""
    items: list[HomeworkItem] = []
    for lesson in diary.get("lesson", []) or []:
        if _lesson_matches_date(lesson, target_date):
            items.extend(_homework_from_lesson(lesson, target_date))
    return items


def parse_grades(diary: dict, target_date: date) -> list[Grade]:
    """Извлекает все оценки за `target_date` из user[0].mark[].

    Сопоставляет lessonId с lesson[] для получения имени предмета.
    """
    grades: list[Grade] = []
    users = diary.get("user") or []
    if not users:
        return grades

    lessons_by_id: dict[int, dict] = {
        lesson.get("id"): lesson for lesson in (diary.get("lesson") or [])
    }

    for mark in users[0].get("mark") or []:
        mark_dt_ms = mark.get("dt")
        if mark_dt_ms is None:
            continue
        mark_date = datetime.fromtimestamp(mark_dt_ms / 1000, tz=TZ).date()
        if mark_date != target_date:
            continue

        lesson = lessons_by_id.get(mark.get("lessonId"))
        subject = (
            (lesson.get("unit") or {}).get("name") if lesson else "Без предмета"
        ) or "Без предмета"

        grades.append(Grade(
            mark_id=mark.get("id"),
            subject=subject,
            value=str(mark.get("mark", "")),
            comment=mark.get("cwtName") or mark.get("workType"),
            target_date=target_date,
        ))
    return grades
