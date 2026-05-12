"""Dataclass'ы для распарсенных сущностей из eschool API."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class HomeworkItem:
    """Одно домашнее задание для одного урока."""
    lesson_id: int
    variant_id: int
    subject: str               # lesson.unit.name
    teacher: str | None        # lesson.teacher.factTeacherIN
    text: str                  # variant.preview или strip(variant.text)
    target_date: date          # дата урока


@dataclass(frozen=True)
class Grade:
    """Одна оценка по предмету."""
    mark_id: int
    subject: str               # имя предмета
    value: str                 # текст оценки ("5", "4", "н" — что вернёт API)
    comment: str | None        # тип работы, если есть
    target_date: date          # дата урока, к которому оценка
