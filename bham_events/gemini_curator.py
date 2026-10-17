"""Gemini 3.8 Flash + Google Search Grounding curator for Birmingham, AL events."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from google import genai
from rich.console import Console

from .config import AppConfig, load_interests
from .models import DigestPayload, EventItem

console = Console()


def _build_digest_json_schema() -> dict:
    """Returns a clean JSON Schema compatible with Gemini Interactions API structured output."""
    return {
        "type": "object",
        "properties": {
            "headline": {
                "type": "string",
                "description": "Catchy editorial headline for this Birmingham event digest",
            },
            "intro_note": {
                "type": "string",
                "description": "2-3 sentence friendly summary highlighting top picks across music, comedy, food, and theater",
            },
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "category": {
                            "type": "string",
                            "enum": ["music", "comedy_podcast", "food", "theater_play", "fun_local"],
                        },
                        "venue": {"type": "string"},
                        "start_date": {
                            "type": "string",
                            "description": "YYYY-MM-DD format",
                        },
                        "start_time": {
                            "type": "string",
                            "description": "24h HH:MM format in America/Chicago (e.g. 19:30)",
                        },
                        "end_time": {
                            "type": "string",
                            "description": "24h HH:MM format in America/Chicago (e.g. 22:00)",
                        },
                        "price_info": {"type": "string"},
                        "url": {"type": "string"},
                        "description": {"type": "string"},
                        "match_reason": {"type": "string"},
                        "relevance_score": {"type": "integer"},
                        "is_ytmusic_match": {"type": "boolean"},
                    },
                    "required": [
                        "title",
                        "category",
                        "venue",
                        "start_date",
                        "start_time",
                        "end_time",
                        "price_info",
                        "url",
                        "description",
                        "match_reason",
                        "relevance_score",
                        "is_ytmusic_match",
                    ],
                },
            },
        },
        "required": ["headline", "intro_note", "events"],
    }


def discover_and_curate_events(
    config: AppConfig,
    scraped_context: str,
    ytmusic_profile: dict[str, list[str]],
) -> DigestPayload:
    """
    Uses `gemini-3.8-flash` via the Interactions API with `google_search` grounding
    and structured JSON output to discover, cross-reference, and rank Birmingham events.
    """
    if not config.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Please set GEMINI_API_KEY in your .env file."
        )

    client = genai.Client(api_key=config.gemini_api_key)
    interests = load_interests(config)

    today = datetime.now()
    end_window = today + timedelta(days=config.lookahead_days)
    today_str = today.strftime("%Y-%m-%d")
    end_str = end_window.strftime("%Y-%m-%d")

    artists_sample = ", ".join(ytmusic_profile.get("artists", [])[:100]) or "Indie rock, soul, Americana, alternative, live bands"
    podcasts_sample = ", ".join(ytmusic_profile.get("podcasts", [])[:60]) or "Stand-up comedians, comedy podcasts, storytelling"
    venues_sample = ", ".join(interests.get("favorite_venues", []))

    system_instruction = (
        "You are an expert local event scout and cultural curator for Birmingham, Alabama (USA). "
        "Your job is to find real, verified upcoming events in the Greater Birmingham area "
        f"occurring between {today_str} and {end_str} and match them to the user's tastes."
    )

    prompt = f"""
Find and curate the best upcoming events in **Birmingham, Alabama** from **{today_str} to {end_str}** (next {config.lookahead_days} days).

### User Taste Profile (from YouTube Music & Preferences)
- **YouTube Music Artists / Bands**: {artists_sample}
- **Podcast Comedians & Comedy Tastes**: {podcasts_sample}
- **Favorite Birmingham Venues**: {venues_sample}

### What to Search & Include (5 Categories)
1. **`music`**: Concerts at Saturn, Iron City, Avondale Brewing, WorkPlay, Coca-Cola Amphitheater, BJCC, The Nick, Alabama Theatre, Lyric Theatre. Highlight any artist that directly matches or sounds similar to the user's YouTube Music library (`is_ytmusic_match: true`).
2. **`comedy_podcast`**: Stand-up comedians (especially touring podcast comedians), live podcast tapings, or comedy shows at Stardome Comedy Club, Lyric Theatre, Alabama Theatre, BJCC, or Saturn.
3. **`food`**: Birmingham food festivals, pop-ups, wine/beer tastings, Pepper Place Market special events, Greek Food Festival, BBQ/culinary events.
4. **`theater_play`**: Good plays, musicals, Broadway in Birmingham (BJCC), Red Mountain Theatre, Virginia Samford Theatre, Terrific New Theatre, Alabama Shakespeare Festival (if major), or Alys Stephens Center productions.
5. **`fun_local`**: Unique, high-energy Birmingham community events, art walks, trivia/game nights at Saturn, Barons/Legion/Stallions special nights, Railroad Park events, or quirky local happenings.

### Instructions
- Use **Google Search** actively to verify upcoming {today_str} to {end_str} schedules for Birmingham, AL venues and cross-check the scraped venue data below.
- Only include events taking place on or after `{today_str}`.
- Aim for **12 to 20 high-quality, diverse events** across all 5 categories.
- Ensure every event has a valid `YYYY-MM-DD` `start_date`, 24-hour `start_time` (e.g. `19:30`), venue name, ticket/event URL, and a specific `match_reason`.

### Scraped Venue Context
{scraped_context[:28000]}
"""

    console.print(
        f"[cyan]Running Gemini ({config.gemini_model}) with Google Search grounding "
        f"for Birmingham events ({today_str} -> {end_str})...[/cyan]"
    )

    interaction = client.interactions.create(
        model=config.gemini_model,
        system_instruction=system_instruction,
        input=prompt,
        tools=[{"type": "google_search"}],
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": _build_digest_json_schema(),
        },
    )

    raw_text = (interaction.output_text or "").strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()

    data = json.loads(raw_text)
    payload = DigestPayload.model_validate(data)
    # Sort by relevance score descending, then start_date ascending
    payload.events.sort(key=lambda e: (-e.relevance_score, e.start_date))
    return payload
