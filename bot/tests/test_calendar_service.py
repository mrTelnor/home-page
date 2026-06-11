"""Тесты calendar_service: парсинг событий, выбор напоминаний, дедуп, форматтеры.

Google API мокается (build/credentials), файл состояния — tmp_path.
"""
import base64
import json
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app import calendar_service as cs
from app.calendar_service import TZ, CalendarConfig, CalendarEvent


def make_event(
    start: datetime,
    *,
    summary: str = "Событие",
    label: str = "Семья",
    cal_id: str = "cal1",
    event_id: str = "e1",
    all_day: bool = False,
    reminders: tuple[int, ...] = (),
) -> CalendarEvent:
    return CalendarEvent(
        calendar_label=label,
        calendar_id=cal_id,
        event_id=event_id,
        summary=summary,
        start=start,
        end=None,
        is_all_day=all_day,
        reminders_minutes=reminders,
    )


@pytest.fixture
def state_path(tmp_path, monkeypatch):
    path = tmp_path / "state" / "sent_reminders.json"
    monkeypatch.setattr(cs.settings, "reminders_data_path", str(path))
    return path


# --- load_calendars ---


def test_load_calendars_empty(monkeypatch):
    monkeypatch.setattr(cs.settings, "calendar_configs", "  ")
    assert cs.load_calendars() == []


def test_load_calendars_invalid_json(monkeypatch):
    monkeypatch.setattr(cs.settings, "calendar_configs", "{not json")
    assert cs.load_calendars() == []


def test_load_calendars_ok(monkeypatch):
    monkeypatch.setattr(
        cs.settings,
        "calendar_configs",
        '[{"label": "Семья", "id": "fam@group"}, {"label": "Работа", "id": "work@group"}]',
    )
    cals = cs.load_calendars()
    assert cals == [
        CalendarConfig(label="Семья", id="fam@group"),
        CalendarConfig(label="Работа", id="work@group"),
    ]


# --- _build_service ---


def test_build_service_no_credentials(monkeypatch):
    monkeypatch.setattr(cs.settings, "google_service_account_b64", "")
    assert cs._build_service() is None


def test_build_service_bad_b64(monkeypatch):
    monkeypatch.setattr(cs.settings, "google_service_account_b64", "%%%not-base64%%%")
    assert cs._build_service() is None


def test_build_service_ok(monkeypatch):
    info = {"type": "service_account", "project_id": "test"}
    b64 = base64.b64encode(json.dumps(info).encode()).decode()
    monkeypatch.setattr(cs.settings, "google_service_account_b64", b64)

    fake_creds = object()
    fake_sa = MagicMock()
    fake_sa.Credentials.from_service_account_info.return_value = fake_creds
    monkeypatch.setattr(cs, "service_account", fake_sa)

    fake_service = object()
    build_mock = MagicMock(return_value=fake_service)
    monkeypatch.setattr(cs, "build", build_mock)

    assert cs._build_service() is fake_service
    fake_sa.Credentials.from_service_account_info.assert_called_once_with(info, scopes=cs.SCOPES)
    build_mock.assert_called_once_with("calendar", "v3", credentials=fake_creds, cache_discovery=False)


# --- _parse_event_start ---


def test_parse_event_start_timed():
    raw = {
        "start": {"dateTime": "2026-06-11T15:00:00+03:00"},
        "end": {"dateTime": "2026-06-11T16:30:00+03:00"},
    }
    start, end, is_all_day = cs._parse_event_start(raw)
    assert not is_all_day
    assert start == datetime(2026, 6, 11, 15, 0, tzinfo=TZ)
    assert end == datetime(2026, 6, 11, 16, 30, tzinfo=TZ)


def test_parse_event_start_timed_without_end():
    raw = {"start": {"dateTime": "2026-06-11T15:00:00+03:00"}, "end": {}}
    start, end, is_all_day = cs._parse_event_start(raw)
    assert end is None
    assert not is_all_day


def test_parse_event_start_all_day():
    raw = {"start": {"date": "2026-06-11"}, "end": {"date": "2026-06-12"}}
    start, end, is_all_day = cs._parse_event_start(raw)
    assert is_all_day
    assert start == datetime(2026, 6, 11, 0, 0, tzinfo=TZ)
    assert end == datetime(2026, 6, 12, 0, 0, tzinfo=TZ)


def test_parse_event_start_all_day_without_end():
    raw = {"start": {"date": "2026-06-11"}, "end": {}}
    start, end, is_all_day = cs._parse_event_start(raw)
    assert is_all_day
    assert end is None


# --- _default_reminders / _extract_reminders ---


def test_default_reminders_empty(monkeypatch):
    monkeypatch.setattr(cs.settings, "calendar_default_reminders_min", " ")
    assert cs._default_reminders() == ()


def test_default_reminders_parsed(monkeypatch):
    monkeypatch.setattr(cs.settings, "calendar_default_reminders_min", "30, 15")
    assert cs._default_reminders() == (30, 15)


def test_default_reminders_invalid(monkeypatch):
    monkeypatch.setattr(cs.settings, "calendar_default_reminders_min", "abc,15")
    assert cs._default_reminders() == ()


def test_extract_reminders_overrides():
    raw = {"reminders": {"useDefault": False, "overrides": [{"minutes": 10}, {"minutes": 30}, {"method": "email"}]}}
    assert cs._extract_reminders(raw) == (10, 30)


def test_extract_reminders_falls_back_to_default(monkeypatch):
    monkeypatch.setattr(cs.settings, "calendar_default_reminders_min", "45")
    assert cs._extract_reminders({}) == (45,)
    assert cs._extract_reminders({"reminders": {"useDefault": True}}) == (45,)


# --- _fetch_events / fetch_events ---


def _service_with_items(items: list[dict]) -> MagicMock:
    service = MagicMock()
    service.events.return_value.list.return_value.execute.return_value = {"items": items}
    return service


def test_fetch_events_for_calendar(monkeypatch):
    monkeypatch.setattr(cs.settings, "calendar_default_reminders_min", "30")
    items = [
        {
            "id": "ev1",
            "summary": "Врач",
            "start": {"dateTime": "2026-06-11T15:00:00+03:00"},
            "end": {"dateTime": "2026-06-11T16:00:00+03:00"},
            "reminders": {"overrides": [{"minutes": 20}]},
        },
        {"id": "ev2", "status": "cancelled"},
        {"id": "ev3", "start": {}, "end": {}},  # invalid date → skip
        {
            "id": "ev4",
            "start": {"date": "2026-06-12"},
            "end": {"date": "2026-06-13"},
        },
    ]
    service = _service_with_items(items)
    cal = CalendarConfig(label="Семья", id="fam@group")
    now = datetime.now(TZ)

    events = cs._fetch_events(service, cal, now, now + timedelta(days=1))

    assert [e.event_id for e in events] == ["ev1", "ev4"]
    assert events[0].summary == "Врач"
    assert events[0].reminders_minutes == (20,)
    assert not events[0].is_all_day
    assert events[1].summary == "(без названия)"
    assert events[1].is_all_day
    assert events[1].reminders_minutes == (30,)
    list_kwargs = service.events.return_value.list.call_args.kwargs
    assert list_kwargs["calendarId"] == "fam@group"
    assert list_kwargs["singleEvents"] is True


def test_fetch_events_no_service(monkeypatch):
    monkeypatch.setattr(cs, "_build_service", lambda: None)
    now = datetime.now(TZ)
    assert cs.fetch_events(now, now + timedelta(hours=1)) == []


def test_fetch_events_aggregates_and_survives_errors(monkeypatch):
    monkeypatch.setattr(cs, "_build_service", lambda: object())
    monkeypatch.setattr(
        cs.settings,
        "calendar_configs",
        '[{"label": "A", "id": "a"}, {"label": "B", "id": "bad"}]',
    )
    event = make_event(datetime.now(TZ), cal_id="a")

    def fake_fetch(service, cal, time_min, time_max):
        if cal.id == "bad":
            raise RuntimeError("boom")
        return [event]

    monkeypatch.setattr(cs, "_fetch_events", fake_fetch)
    now = datetime.now(TZ)

    assert cs.fetch_events(now, now + timedelta(hours=1)) == [event]


# --- state file: _load_sent / _save_sent / _prune_old ---


def test_load_sent_missing_file(state_path):
    assert cs._load_sent() == {}


def test_load_sent_corrupt_file(state_path):
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("{broken", encoding="utf-8")
    assert cs._load_sent() == {}


def test_save_and_load_roundtrip(state_path):
    data = {"k": datetime.now(TZ).isoformat()}
    cs.save_sent(data)
    assert cs._load_sent() == data


def test_prune_old_drops_stale_and_invalid():
    now = datetime.now(TZ)
    data = {
        "fresh": now.isoformat(),
        "stale": (now - timedelta(days=10)).isoformat(),
        "garbage": "not-a-date",
    }
    assert cs._prune_old(data) == {"fresh": data["fresh"]}


# --- select_reminders_to_send ---


def test_select_reminders_hour_reminder(state_path):
    now = datetime.now(TZ)
    event = make_event(now + timedelta(minutes=60))

    to_send, sent = cs.select_reminders_to_send(now, [event])

    assert [(e.event_id, label) for e, label in to_send] == [("e1", "за 1 час")]
    key = f"60min:cal1:e1:{event.start.isoformat()}"
    assert key in sent


def test_select_reminders_dedup(state_path):
    now = datetime.now(TZ)
    event = make_event(now + timedelta(minutes=60))
    key = f"60min:cal1:e1:{event.start.isoformat()}"
    cs.save_sent({key: now.isoformat()})

    to_send, _ = cs.select_reminders_to_send(now, [event])

    assert to_send == []


def test_select_reminders_custom_minutes(state_path):
    now = datetime.now(TZ)
    # 60 в reminders_minutes пропускается (уже покрыт forced-напоминанием)
    event = make_event(now + timedelta(minutes=30), reminders=(60, 30))

    to_send, sent = cs.select_reminders_to_send(now, [event])

    assert [(e.event_id, label) for e, label in to_send] == [("e1", "за 30 мин")]
    assert f"custom-30:cal1:e1:{event.start.isoformat()}" in sent


def test_select_reminders_outside_window(state_path):
    now = datetime.now(TZ)
    event = make_event(now + timedelta(minutes=200), reminders=(30,))

    to_send, _ = cs.select_reminders_to_send(now, [event])

    assert to_send == []


# --- mark_digest_sent / mark_event_sent / has_event_sent ---


def test_mark_digest_sent_once(state_path):
    target = date(2026, 6, 11)
    assert cs.mark_digest_sent(target) is True
    assert cs.mark_digest_sent(target) is False


def test_mark_event_sent_once(state_path):
    assert cs.mark_event_sent("voting_opened:m1") is True
    assert cs.mark_event_sent("voting_opened:m1") is False


def test_has_event_sent(state_path):
    assert cs.has_event_sent("k1") is False
    cs.mark_event_sent("k1")
    assert cs.has_event_sent("k1") is True


# --- formatters ---


def test_format_event_line_timed():
    event = make_event(datetime(2026, 6, 11, 15, 30, tzinfo=TZ), summary="Врач")
    line = cs.format_event_line(event)
    assert "15:30" in line
    assert "Врач" in line
    assert "[Семья]" in line


def test_format_event_line_all_day():
    event = make_event(datetime(2026, 6, 11, tzinfo=TZ), all_day=True)
    assert "весь день" in cs.format_event_line(event)


def test_format_single_reminder_timed():
    event = make_event(datetime(2026, 6, 11, 15, 30, tzinfo=TZ), summary="Врач")
    text = cs.format_single_reminder(event, "за 1 час")
    assert "за 1 час" in text
    assert "Врач" in text
    assert "15:30" in text


def test_format_single_reminder_all_day():
    event = make_event(datetime(2026, 6, 11, tzinfo=TZ), all_day=True)
    text = cs.format_single_reminder(event, "за 30 мин")
    assert "11.06" in text


def test_format_digest_no_events():
    text = cs.format_digest([], [])
    assert "Доброе утро" in text
    assert text.count("событий нет") == 2


def test_format_digest_with_events():
    today = datetime.now(TZ).replace(hour=10, minute=0)
    today_event = make_event(today, summary="Сегодняшнее")
    tomorrow_event = make_event(today + timedelta(days=1), summary="Завтрашнее")
    text = cs.format_digest([today_event], [tomorrow_event])
    assert "Сегодняшнее" in text
    assert "Завтрашнее" in text
    assert "событий нет" not in text


def test_format_digest_menu_collecting():
    menu = {"status": "collecting", "recipes": [{"recipe_id": "r1", "title": "Борщ"}]}
    text = cs.format_digest([], [], menu=menu)
    assert "меню дня готово" in text.lower()
    assert "Борщ" in text
    assert "/suggest" in text


def test_format_digest_menu_voting():
    menu = {
        "status": "voting",
        "recipes": [{"recipe_id": "r1", "title": "Борщ", "votes_count": 2}],
    }
    text = cs.format_digest([], [], menu=menu)
    assert "Голосование за ужин открыто" in text
    assert "Борщ — 2 гол." in text
    assert "/vote" in text


def test_format_digest_menu_closed_with_winner():
    menu = {
        "status": "closed",
        "winner_recipe_id": "r1",
        "recipes": [
            {"recipe_id": "r1", "title": "Борщ", "votes_count": 3},
            {"recipe_id": "r2", "title": "Плов", "votes_count": 1},
        ],
    }
    text = cs.format_digest([], [], menu=menu)
    assert "Победитель ужина:</b> Борщ" in text
    assert "Борщ — 3 гол. 🏆" in text


def test_format_digest_menu_closed_without_winner():
    menu = {
        "status": "closed",
        "winner_recipe_id": None,
        "recipes": [{"recipe_id": "r1", "title": "Борщ", "votes_count": 0}],
    }
    text = cs.format_digest([], [], menu=menu)
    assert "Меню дня" in text
    assert "🏆" not in text


def test_format_digest_menu_without_recipes_ignored():
    text = cs.format_digest([], [], menu={"status": "collecting", "recipes": []})
    assert "Меню" not in text


# --- fetch_digest_events ---


def test_fetch_digest_events_filters_and_sorts(monkeypatch):
    today = datetime.now(TZ).replace(hour=12, minute=0, second=0, microsecond=0)
    e_today_late = make_event(today.replace(hour=18), event_id="t2")
    e_today_early = make_event(today.replace(hour=9), event_id="t1")
    e_tomorrow = make_event(today + timedelta(days=1), event_id="tm")
    e_later = make_event(today + timedelta(days=2), event_id="later")

    captured = {}

    def fake_fetch(time_min, time_max):
        captured["window"] = (time_min, time_max)
        return [e_today_late, e_today_early, e_tomorrow, e_later]

    monkeypatch.setattr(cs, "fetch_events", fake_fetch)

    today_events, tomorrow_events = cs.fetch_digest_events()

    assert [e.event_id for e in today_events] == ["t1", "t2"]
    assert [e.event_id for e in tomorrow_events] == ["tm"]
    time_min, time_max = captured["window"]
    assert time_max - time_min == timedelta(days=2)
