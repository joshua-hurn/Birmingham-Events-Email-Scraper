"""Direct HTML / JSON-LD / RSS scraper for key Birmingham, AL venues and event calendars."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any
import httpx
from bs4 import BeautifulSoup
from rich.console import Console

console = Console()


@dataclass
class VenueSource:
    name: str
    category: str
    url: str


BIRMINGHAM_SOURCES: list[VenueSource] = [
    # Live Music & Concerts
    VenueSource("Saturn Birmingham", "music", "https://saturnbirmingham.com/calendar/"),
    VenueSource("Iron City Bham", "music", "https://ironcitybham.com/events/"),
    VenueSource("Avondale Brewing Company", "music", "https://www.avondalebrewing.com/calendar-tickets"),
    VenueSource("WorkPlay", "music", "https://workplay.com/events/"),
    VenueSource("The Nick", "music", "https://www.thenickrocks.com/events/"),
    VenueSource("BJCC (Legacy Arena & Concert Hall)", "music", "https://www.bjcc.org/upcoming-events.php"),
    # Comedy & Podcasts
    VenueSource("Stardome Comedy Club", "comedy_podcast", "https://www.stardome.com/"),
    VenueSource("Lyric Theatre Birmingham", "comedy_podcast", "https://lyricbham.com/events/"),
    VenueSource("Alabama Theatre", "theater_play", "https://alabamatheatre.com/events/"),
    # Theater & Plays
    VenueSource("Red Mountain Theatre", "theater_play", "https://www.redmountaintheatre.org/season-tickets-shows/"),
    VenueSource("Virginia Samford Theatre", "theater_play", "https://www.virginiasamfordtheatre.org/events/"),
    VenueSource("Terrific New Theatre", "theater_play", "https://terrificnewtheatre.com/"),
    VenueSource("Alys Stephens Center", "theater_play", "https://www.alysstephens.org/events/"),
    # Local / Food / Fun Community Aggregators
    VenueSource("Bham Now Events", "fun_local", "https://bhamnow.com/events/"),
    VenueSource("InBirmingham Events", "fun_local", "https://www.inbirmingham.com/events/"),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _extract_jsonld_events(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Extracts Schema.org Event objects embedded in <script type='application/ld+json'>."""
    extracted: list[dict[str, Any]] = []
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue

        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            if isinstance(graph, list):
                items.extend(g for g in graph if isinstance(g, dict))
            item_type = str(item.get("@type", ""))
            if "Event" in item_type:
                extracted.append(
                    {
                        "name": item.get("name"),
                        "startDate": item.get("startDate"),
                        "endDate": item.get("endDate"),
                        "url": item.get("url"),
                        "description": (item.get("description") or "")[:300],
                        "location": (
                            item.get("location", {}).get("name")
                            if isinstance(item.get("location"), dict)
                            else str(item.get("location", ""))
                        ),
                    }
                )
    return extracted


def _extract_clean_text(soup: BeautifulSoup, max_chars: int = 3500) -> str:
    """Extracts compact, readable text snippets from a venue page."""
    for tag in soup(["script", "style", "noscript", "svg", "footer", "nav"]):
        tag.decompose()
    text = soup.get_text(separator=" | ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text[:max_chars]


async def _fetch_single_source(client: httpx.AsyncClient, source: VenueSource) -> str:
    try:
        resp = await client.get(source.url, timeout=12.0, follow_redirects=True)
        if resp.status_code >= 400:
            return f"### {source.name} ({source.url})\n[Status {resp.status_code} - rely on Google Search for this venue]\n"

        soup = BeautifulSoup(resp.text, "html.parser")
        jsonld = _extract_jsonld_events(soup)
        snippet = _extract_clean_text(soup, max_chars=2800)

        parts = [f"### {source.name} | Category: {source.category} | URL: {source.url}"]
        if jsonld:
            parts.append("Structured JSON-LD Events: " + json.dumps(jsonld[:25], ensure_ascii=False))
        parts.append(f"Page Snippet: {snippet}")
        return "\n".join(parts)
    except Exception as exc:
        return f"### {source.name} ({source.url})\n[Direct fetch skipped ({type(exc).__name__}) - rely on Google Search]\n"


async def scrape_all_birmingham_venues() -> str:
    """Scrapes all configured Birmingham venue pages concurrently and returns a combined context block."""
    console.print(f"[cyan]Scraping {len(BIRMINGHAM_SOURCES)} local Birmingham venues & calendars...[/cyan]")
    async with httpx.AsyncClient(headers=HEADERS, verify=False) as client:
        results = await asyncio.gather(
            *[_fetch_single_source(client, src) for src in BIRMINGHAM_SOURCES]
        )
    return "\n\n".join(results)
