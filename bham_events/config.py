"""Configuration and environment management for the Birmingham Event Scraper."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
ICS_EVENTS_DIR = OUTPUT_DIR / "ics"


@dataclass
class SMTPConfig:
    host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "1025")))
    username: str = field(default_factory=lambda: os.getenv("SMTP_USERNAME", ""))
    password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    use_starttls: bool = field(
        default_factory=lambda: os.getenv("SMTP_STARTTLS", "true").lower() in ("1", "true", "yes")
    )
    use_ssl: bool = field(
        default_factory=lambda: os.getenv("SMTP_SSL", "false").lower() in ("1", "true", "yes")
    )
    verify_cert: bool = field(
        default_factory=lambda: os.getenv("SMTP_VERIFY_CERT", "false").lower() in ("1", "true", "yes")
    )
    sender_email: str = field(default_factory=lambda: os.getenv("EMAIL_FROM", ""))
    recipient_email: str = field(default_factory=lambda: os.getenv("EMAIL_TO", ""))


@dataclass
class AppConfig:
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.8-flash"))
    city: str = field(default_factory=lambda: os.getenv("EVENT_CITY", "Birmingham, AL"))
    lookahead_days: int = field(default_factory=lambda: int(os.getenv("LOOKAHEAD_DAYS", "30")))
    ytmusic_auth_file: Path = field(
        default_factory=lambda: Path(os.getenv("YTMUSIC_AUTH_FILE", str(DATA_DIR / "ytmusic_auth.json")))
    )
    interests_file: Path = field(
        default_factory=lambda: Path(os.getenv("INTERESTS_FILE", str(DATA_DIR / "interests.json")))
    )
    seen_events_db: Path = field(
        default_factory=lambda: Path(os.getenv("SEEN_EVENTS_DB", str(DATA_DIR / "events.db")))
    )
    calendar_feed_url: str = field(
        default_factory=lambda: os.getenv("PROTON_ICS_FEED_URL", "")
    )
    smtp: SMTPConfig = field(default_factory=SMTPConfig)

    def ensure_dirs(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ICS_EVENTS_DIR.mkdir(parents=True, exist_ok=True)


DEFAULT_INTERESTS = {
    "favorite_artists": [],
    "podcast_comedians": [
        "Nate Bargatze",
        "Theo Von",
        "Shane Gillis",
        "Taylor Tomlinson",
        "Matt McCusker",
        "Stavros Halkias",
        "Mark Normand",
        "Sam Morril",
        "Dan Soder",
        "Conan O'Brien",
        "Rory Scovel",
        "Tig Notaro",
        "Fortune Feimster",
        "Dusty Slay",
    ],
    "event_categories": [
        "Live Music & Concerts",
        "Stand-up Comedy & Live Podcasts",
        "Food Festivals, Pop-ups & Culinary Events",
        "Local & Touring Theater / Broadway / Plays",
        "Fun & Unique Local Birmingham Events",
    ],
    "favorite_venues": [
        "Saturn Birmingham",
        "Iron City Bham",
        "Avondale Brewing Company",
        "The Nick",
        "WorkPlay",
        "Coca-Cola Amphitheater",
        "BJCC Concert Hall & Legacy Arena",
        "Alabama Theatre",
        "Lyric Theatre",
        "Stardome Comedy Club",
        "Red Mountain Theatre",
        "Virginia Samford Theatre",
        "Terrific New Theatre",
        "Alys Stephens Center",
        "Pepper Place",
        "Railroad Park",
    ],
}


def load_interests(config: AppConfig) -> dict:
    """Loads user interests from data/interests.json, creating defaults if missing."""
    config.ensure_dirs()
    if not config.interests_file.exists():
        config.interests_file.write_text(json.dumps(DEFAULT_INTERESTS, indent=2), encoding="utf-8")
        return dict(DEFAULT_INTERESTS)
    try:
        return json.loads(config.interests_file.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_INTERESTS)
