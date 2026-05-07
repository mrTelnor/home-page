"""Google Calendar integration for the bot.

Reads events from a list of configured calendars and emits Telegram reminders.

Three reminder types:
- 60-minute reminder before an event starts (forced for every event)
- Custom reminders set on the event itself (event.reminders.overrides)
- Daily digest at 09:00 listing today's and tomorrow's events
"""
from __future__ import annotations

import base64
import json
import logging
import zoneinfo
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
TZ = zoneinfo.ZoneInfo("Europe/Moscow")
HOUR_REMINDER_MIN = 60
HOUR_REMINDER_TOLERANCE_MIN = 4  # window for cron jitter


@dataclass(frozen=True)
class CalendarConfig:
    label: str
    id: str


@dataclass(frozen=True)
class CalendarEvent:
    calendar_label: str
    calendar_id: str
    event_id: str
    summary: str
    start: datetime
    end: datetime | None
    is_all_day: bool
    reminders_minutes: tuple[int, ...]


def load_calendars() -> list[CalendarConfig]:
    raw = settings.calendar_configs.strip()
    if not raw:
        return []
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        logger.exception("Failed to parse CALENDAR_CONFIGS")
        return []
    return [CalendarConfig(label=item["label"], id=item["id"]) for item in items]


def _build_service():
    if not settings.google_service_account_b64:
        return None
    try:
        info = json.loads(base64.b64decode(settings.google_service_account_b64))
    except Exception:
        logger.exception("Failed to decode GOOGLE_SERVICE_ACCOUNT_B64")
        return None
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _parse_event_start(raw_event: dict) -> tuple[datetime, datetime | None, bool]:
    start_field = raw_event.get("start", {})
    end_field = raw_event.get("end", {})
    if "dateTime" in start_field:
        start = datetime.fromisoformat(start_field["dateTime"]).astimezone(TZ)
        end_raw = end_field.get("dateTime")
        end = datetime.fromisoformat(end_raw).astimezone(TZ) if end_raw else None
        return start, end, False
    # all-day event: 'date' field, value is YYYY-MM-DD
    day = date.fromisoformat(start_field["date"])
    start = datetime.combine(day, datetime.min.time(), tzinfo=TZ)
    end_raw = end_field.get("date")
    end = (
        datetime.combine(date.fromisoformat(end_raw), datetime.min.time(), tzinfo=TZ)
        if end_raw else None
    )
    return start, end, True


def _extract_reminders(raw_event: dict) -> tuple[int, ...]:
    """Return list of minute offsets from custom reminder overrides."""
    reminders = raw_event.get("reminders", {})
    if reminders.get("useDefault"):
        return ()
    overrides = reminders.get("overrides") or []
    return tuple(int(o["minutes"]) for o in overrides if "minutes" in o)


def _fetch_events(service, cal: CalendarConfig, time_min: datetime, time_max: datetime) -> list[CalendarEvent]:
    raw = service.events().list(
        calendarId=cal.id,
        timeMin=time_min.isoformat(),
        timeMax=time_max.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=100,
    ).execute()

    events = []
    for item in raw.get("items", []):
        if item.get("status") == "cancelled":
            continue
        try:
            start, end, is_all_day = _parse_event_start(item)
        except (KeyError, ValueError):
            logger.warning("Skipping event with invalid date: %s", item.get("id"))
            continue
        events.append(CalendarEvent(
            calendar_label=cal.label,
            calendar_id=cal.id,
            event_id=item["id"],
            summary=item.get("summary", "(без названия)"),
            start=start,
            end=end,
            is_all_day=is_all_day,
            reminders_minutes=_extract_reminders(item),
        ))
    return events


def fetch_events(time_min: datetime, time_max: datetime) -> list[CalendarEvent]:
    """Fetch events from all configured calendars in a time window."""
    service = _build_service()
    if service is None:
        return []
    calendars = load_calendars()
    all_events: list[CalendarEvent] = []
    for cal in calendars:
        try:
            all_events.extend(_fetch_events(service, cal, time_min, time_max))
        except Exception:
            logger.exception("Failed to fetch events for %s", cal.id)
    return all_events


# ─── Reminder dedup ────────────────────────────────────────────────────────

def _load_sent() -> dict[str, str]:
    path = Path(settings.reminders_data_path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("Could not read %s, resetting", path)
        return {}


def _save_sent(data: dict[str, str]) -> None:
    path = Path(settings.reminders_data_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _prune_old(data: dict[str, str], cutoff_days: int = 7) -> dict[str, str]:
    cutoff = datetime.now(TZ) - timedelta(days=cutoff_days)
    pruned = {}
    for key, ts in data.items():
        try:
            sent_at = datetime.fromisoformat(ts)
        except ValueError:
            continue
        if sent_at >= cutoff:
            pruned[key] = ts
    return pruned


# ─── Reminder selection ────────────────────────────────────────────────────

def select_reminders_to_send(now: datetime, events: list[CalendarEvent]) -> tuple[list[tuple[CalendarEvent, str]], dict[str, str]]:
    """For each event, decide which reminders to fire now.

    Returns ([(event, reminder_label), ...], updated_sent_dict).
    Skips reminders already in the sent dict.
    """
    sent = _prune_old(_load_sent())
    to_send: list[tuple[CalendarEvent, str]] = []

    for event in events:
        # Forced 1-hour reminder
        delta_min = (event.start - now).total_seconds() / 60
        if HOUR_REMINDER_MIN - HOUR_REMINDER_TOLERANCE_MIN <= delta_min <= HOUR_REMINDER_MIN + HOUR_REMINDER_TOLERANCE_MIN:
            key = f"60min:{event.calendar_id}:{event.event_id}:{event.start.isoformat()}"
            if key not in sent:
                to_send.append((event, "за 1 час"))
                sent[key] = now.isoformat()

        # Custom event reminders
        for minutes in event.reminders_minutes:
            if minutes == HOUR_REMINDER_MIN:
                continue  # already covered
            if minutes - HOUR_REMINDER_TOLERANCE_MIN <= delta_min <= minutes + HOUR_REMINDER_TOLERANCE_MIN:
                key = f"custom-{minutes}:{event.calendar_id}:{event.event_id}:{event.start.isoformat()}"
                if key not in sent:
                    to_send.append((event, f"за {minutes} мин"))
                    sent[key] = now.isoformat()

    return to_send, sent


def mark_digest_sent(target_date: date) -> bool:
    """Returns True if digest for `target_date` was not yet sent and now is recorded."""
    sent = _prune_old(_load_sent())
    key = f"digest:{target_date.isoformat()}"
    if key in sent:
        return False
    sent[key] = datetime.now(TZ).isoformat()
    _save_sent(sent)
    return True


def save_sent(data: dict[str, str]) -> None:
    _save_sent(data)


# ─── Formatters ────────────────────────────────────────────────────────────

def format_event_line(event: CalendarEvent) -> str:
    if event.is_all_day:
        time_str = "весь день"
    else:
        time_str = event.start.astimezone(TZ).strftime("%H:%M")
    return f"  • <b>{time_str}</b> — {event.summary} <i>[{event.calendar_label}]</i>"


def format_single_reminder(event: CalendarEvent, reminder_label: str) -> str:
    when = event.start.astimezone(TZ).strftime("%H:%M")
    if event.is_all_day:
        when = event.start.astimezone(TZ).strftime("%d.%m")
    return (
        f"⏰ Напоминание {reminder_label}\n\n"
        f"<b>{event.summary}</b>\n"
        f"🗓 {when} <i>[{event.calendar_label}]</i>"
    )


def format_digest(today_events: list[CalendarEvent], tomorrow_events: list[CalendarEvent]) -> str:
    lines = ["☀️ <b>Доброе утро! Расписание на сегодня и завтра:</b>", ""]

    today = datetime.now(TZ).date()
    lines.append(f"<b>Сегодня ({today.strftime('%d.%m')}):</b>")
    if today_events:
        lines.extend(format_event_line(e) for e in today_events)
    else:
        lines.append("  — событий нет")

    lines.append("")
    tomorrow = today + timedelta(days=1)
    lines.append(f"<b>Завтра ({tomorrow.strftime('%d.%m')}):</b>")
    if tomorrow_events:
        lines.extend(format_event_line(e) for e in tomorrow_events)
    else:
        lines.append("  — событий нет")

    return "\n".join(lines)


def fetch_digest_events() -> tuple[list[CalendarEvent], list[CalendarEvent]]:
    """Fetch today's and tomorrow's events for the morning digest."""
    today = datetime.now(TZ).date()
    today_start = datetime.combine(today, datetime.min.time(), tzinfo=TZ)
    after_tomorrow_start = today_start + timedelta(days=2)
    events = fetch_events(today_start, after_tomorrow_start)

    tomorrow = today + timedelta(days=1)
    today_events = [e for e in events if e.start.astimezone(TZ).date() == today]
    tomorrow_events = [e for e in events if e.start.astimezone(TZ).date() == tomorrow]

    today_events.sort(key=lambda e: e.start)
    tomorrow_events.sort(key=lambda e: e.start)
    return today_events, tomorrow_events
