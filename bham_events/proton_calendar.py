"""iCalendar (.ics) generator for Proton Calendar (master feed + individual event files)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from icalendar import Calendar, Event

from .config import AppConfig, ICS_EVENTS_DIR, OUTPUT_DIR
from .models import EventItem

CENTRAL_TZ = ZoneInfo("America/Chicago")

CATEGORY_LABELS = {
    "music": "Live Music",
    "comedy_podcast": "Comedy & Podcasts",
    "food": "Food & Drink",
    "theater_play": "Theater & Plays",
    "fun_local": "Local & Fun",
}


def _parse_dt(date_str: str, time_str: str, default_hour: int = 19) -> datetime:
    """Parses YYYY-MM-DD and HH:MM into a timezone-aware America/Chicago datetime."""
    try:
        year, month, day = [int(x) for x in date_str.strip().split("-")[:3]]
    except Exception:
        now = datetime.now(CENTRAL_TZ)
        year, month, day = now.year, now.month, now.day

    hour, minute = default_hour, 0
    if time_str and ":" in time_str:
        try:
            parts = time_str.strip().split(":")
            hour = int(parts[0])
            minute = int(parts[1][:2])
        except Exception:
            pass

    return datetime(year, month, day, hour, minute, tzinfo=CENTRAL_TZ)


def build_ical_event(item: EventItem) -> Event:
    """Builds a RFC 5545 VEVENT compatible with Proton Calendar."""
    ev = Event()
    cat_label = CATEGORY_LABELS.get(item.category, "Event")
    prefix = "🎵 " if item.category == "music" else (
        "🎙️ " if item.category == "comedy_podcast" else (
            "🍽️ " if item.category == "food" else (
                "🎭 " if item.category == "theater_play" else "✨ "
            )
        )
    )

    ev.add("summary", f"{prefix}{item.title} @ {item.venue}")
    start_dt = _parse_dt(item.start_date, item.start_time, default_hour=19)
    end_dt = _parse_dt(item.start_date, item.end_time, default_hour=22)
    if end_dt <= start_dt:
        end_dt = start_dt + timedelta(hours=2, minutes=30)

    ev.add("dtstart", start_dt)
    ev.add("dtend", end_dt)
    ev.add("dtstamp", datetime.now(ZoneInfo("UTC")))
    ev.add("uid", item.uid)
    ev.add("location", f"{item.venue}, Birmingham, AL")
    ev.add("categories", [cat_label])

    desc_lines = [
        f"Category: {cat_label}",
        f"Why it matched: {item.match_reason}",
        f"Price: {item.price_info}",
        "",
        item.description,
    ]
    if item.url:
        desc_lines.extend(["", f"Tickets / Info: {item.url}"])
        ev.add("url", item.url)

    ev.add("description", "\n".join(desc_lines))
    return ev


def generate_proton_calendar_files(
    config: AppConfig, events: list[EventItem]
) -> tuple[Path, list[tuple[EventItem, Path]]]:
    """
    Generates:
    1. A combined `output/birmingham_events.ics` master calendar file (for one-click import or live URL subscription in Proton Calendar).
    2. Individual `output/ics/<slug>.ics` files for each event so the user can import single events from the review email.
    """
    config.ensure_dirs()

    master_cal = Calendar()
    master_cal.add("prodid", "-//Birmingham Event Curator//brave-fermi//EN")
    master_cal.add("version", "2.0")
    master_cal.add("calscale", "GREGORIAN")
    master_cal.add("method", "PUBLISH")
    master_cal.add("x-wr-calname", "Birmingham Curated Events")
    master_cal.add("x-wr-timezone", "America/Chicago")
    master_cal.add(
        "x-wr-caldesc",
        "Curated Birmingham, AL Music, Comedy Podcasts, Food & Theater Events",
    )

    individual_files: list[tuple[EventItem, Path]] = []

    for item in events:
        vevent = build_ical_event(item)
        master_cal.add_component(vevent)

        single_cal = Calendar()
        single_cal.add("prodid", "-//Birmingham Event Curator//brave-fermi//EN")
        single_cal.add("version", "2.0")
        single_cal.add("calscale", "GREGORIAN")
        single_cal.add("method", "PUBLISH")
        single_cal.add_component(build_ical_event(item))

        single_path = ICS_EVENTS_DIR / f"{item.slug}.ics"
        single_path.write_bytes(single_cal.to_ical())
        individual_files.append((item, single_path))

    master_path = OUTPUT_DIR / "birmingham_events.ics"
    master_path.write_bytes(master_cal.to_ical())

    return master_path, individual_files
