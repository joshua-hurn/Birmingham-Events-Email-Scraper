"""Data models and SQLite persistence for Birmingham events."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field


EventCategory = Literal[
    "music",
    "comedy_podcast",
    "food",
    "theater_play",
    "fun_local",
]


class EventItem(BaseModel):
    title: str = Field(description="Name of the concert, show, play, festival, or event")
    category: EventCategory = Field(
        description="Event category: 'music', 'comedy_podcast', 'food', 'theater_play', or 'fun_local'"
    )
    venue: str = Field(description="Venue name and/or address in the Birmingham, AL area")
    start_date: str = Field(
        description="Event start date in YYYY-MM-DD format (e.g. 2026-10-24)"
    )
    start_time: str = Field(
        default="19:00",
        description="24-hour start time in HH:MM format (America/Chicago), default '19:00' if unspecified",
    )
    end_time: str = Field(
        default="22:00",
        description="24-hour end time in HH:MM format (America/Chicago), default '22:00'",
    )
    price_info: str = Field(
        default="See website",
        description="Ticket price range or admission details (e.g., '$25 - $45', 'Free')",
    )
    url: str = Field(
        default="",
        description="Direct link to tickets, venue event page, or official event listing",
    )
    description: str = Field(
        description="Concise 1-3 sentence engaging summary of what the event is and why it's worth going"
    )
    match_reason: str = Field(
        description="Why this matched the user (e.g., 'Matches your YouTube Music artist: St. Paul & The Broken Bones', 'Podcast comedian at Stardome', 'Major Broadway production at BJCC')"
    )
    relevance_score: int = Field(
        default=80,
        description="Score from 1 to 100 indicating how strongly this matches the user's tastes",
    )
    is_ytmusic_match: bool = Field(
        default=False,
        description="True if this artist/podcast directly matches or closely relates to the user's YouTube Music library",
    )

    @property
    def uid(self) -> str:
        """Stable unique identifier for deduplication and iCalendar UID."""
        norm_title = "".join(c for c in self.title.lower() if c.isalnum())
        norm_date = self.start_date.strip()
        raw = f"{norm_title}-{norm_date}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"bham-event-{digest}@brave-fermi.local"

    @property
    def slug(self) -> str:
        """Filesystem-safe slug for individual .ics files."""
        clean = "".join(c if c.isalnum() else "-" for c in self.title.lower())
        while "--" in clean:
            clean = clean.replace("--", "-")
        clean = clean.strip("-")[:45]
        return f"{self.start_date}_{clean}"


class DigestPayload(BaseModel):
    headline: str = Field(
        description="Catchy editorial headline for this week's Birmingham event digest"
    )
    intro_note: str = Field(
        description="Short, friendly 2-3 sentence overview highlighting the top picks in Birmingham"
    )
    events: list[EventItem] = Field(
        description="Curated, deduplicated list of upcoming Birmingham events sorted by relevance and date"
    )


class EventStore:
    """SQLite store to track previously discovered and emailed events."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    uid TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    venue TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    url TEXT,
                    match_reason TEXT,
                    first_seen_at TEXT NOT NULL,
                    emailed_at TEXT
                )
                """
            )
            conn.commit()

    def is_emailed(self, uid: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT emailed_at FROM events WHERE uid = ? AND emailed_at IS NOT NULL",
                (uid,),
            ).fetchone()
            return row is not None

    def upsert_events(self, events: list[EventItem], mark_emailed: bool = False) -> None:
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            for ev in events:
                emailed_val = now if mark_emailed else None
                conn.execute(
                    """
                    INSERT INTO events (uid, title, category, venue, start_date, start_time, url, match_reason, first_seen_at, emailed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(uid) DO UPDATE SET
                        title = excluded.title,
                        venue = excluded.venue,
                        url = CASE WHEN excluded.url != '' THEN excluded.url ELSE events.url END,
                        emailed_at = COALESCE(events.emailed_at, excluded.emailed_at)
                    """,
                    (
                        ev.uid,
                        ev.title,
                        ev.category,
                        ev.venue,
                        ev.start_date,
                        ev.start_time,
                        ev.url,
                        ev.match_reason,
                        now,
                        emailed_val,
                    ),
                )
            conn.commit()
