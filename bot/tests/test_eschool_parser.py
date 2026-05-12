"""Тесты для bot/app/eschool/parser.py."""
from datetime import date

from app.eschool.parser import parse_homework


def test_parse_homework_filters_by_target_date(diary_sample):
    items = parse_homework(diary_sample, target_date=date(2026, 5, 12))
    # У нас 2 урока с DZ на 2026-05-12: английский и математика
    assert len(items) == 2
    subjects = {item.subject for item in items}
    assert subjects == {"Иностранный язык (английский)", "Математика"}


def test_parse_homework_skips_other_dates(diary_sample):
    items = parse_homework(diary_sample, target_date=date(2026, 5, 13))
    # На 13 мая в фикстуре есть только урок русского без ДЗ
    assert items == []


def test_parse_homework_uses_preview_when_available(diary_sample):
    items = parse_homework(diary_sample, target_date=date(2026, 5, 12))
    english = next(i for i in items if i.subject.startswith("Иностранный"))
    assert english.text == "дз на 12.05 упр.11 стр.81 PB"
    assert english.lesson_id == 9789281
    assert english.variant_id == 5982880
    assert english.teacher == "Вербицкая Маргарита Григорьевна"


def test_parse_homework_skips_lessons_without_dz():
    diary = {
        "lesson": [
            {
                "id": 1,
                "date": 1778533200000,
                "unit": {"name": "Физкультура"},
                "teacher": {"factTeacherIN": "Петров П.П."},
                "part": [{"id": 1, "cat": "RK", "name": "Классная работа", "hasTask": 0}],
                "date_d": "2026-05-12",
            }
        ]
    }
    assert parse_homework(diary, target_date=date(2026, 5, 12)) == []


def test_parse_homework_falls_back_to_html_strip_when_no_preview():
    diary = {
        "lesson": [
            {
                "id": 1,
                "date": 1778533200000,
                "unit": {"name": "Биология"},
                "teacher": {"factTeacherIN": "Сидоров"},
                "part": [
                    {
                        "id": 1,
                        "cat": "DZ",
                        "hasTask": 1,
                        "variant": [
                            {
                                "id": 100,
                                "text": "<p>читать <b>главу 5</b></p>",
                            }
                        ],
                    }
                ],
                "date_d": "2026-05-12",
            }
        ]
    }
    items = parse_homework(diary, target_date=date(2026, 5, 12))
    assert len(items) == 1
    assert items[0].text == "читать главу 5"


def test_parse_homework_skips_when_has_task_zero():
    diary = {
        "lesson": [
            {
                "id": 1,
                "date": 1778533200000,
                "unit": {"name": "ИЗО"},
                "teacher": {"factTeacherIN": "Иванов"},
                "part": [{"id": 1, "cat": "DZ", "hasTask": 0}],
                "date_d": "2026-05-12",
            }
        ]
    }
    assert parse_homework(diary, target_date=date(2026, 5, 12)) == []


def test_parse_grades_uses_dt_for_filtering(diary_sample):
    from app.eschool.parser import parse_grades
    grades = parse_grades(diary_sample, target_date=date(2026, 5, 12))
    assert len(grades) == 2


def test_parse_grades_resolves_subject_via_lesson_id(diary_sample):
    from app.eschool.parser import parse_grades
    grades = parse_grades(diary_sample, target_date=date(2026, 5, 12))
    english = next(g for g in grades if g.subject.startswith("Иностранный"))
    assert english.value == "5"
    assert english.comment == "Контрольная работа"
    math = next(g for g in grades if g.subject == "Математика")
    assert math.value == "4"
    assert math.comment is None


def test_parse_grades_empty_when_no_marks_on_date(diary_sample):
    from app.eschool.parser import parse_grades
    grades = parse_grades(diary_sample, target_date=date(2026, 5, 13))
    assert grades == []


def test_parse_grades_handles_missing_lesson_mapping():
    from app.eschool.parser import parse_grades
    diary = {
        "user": [{"mark": [{"id": 1, "lessonId": 99999, "mark": "3", "dt": 1778533200000}]}],
        "lesson": [],
    }
    grades = parse_grades(diary, target_date=date(2026, 5, 12))
    assert len(grades) == 1
    assert grades[0].subject == "Без предмета"
