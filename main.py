"""CLI Entrypoint for the Birmingham, AL Event Scraper & Proton Calendar Digest."""

from __future__ import annotations

import argparse
import asyncio
import http.server
import socketserver
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from rich.console import Console
from rich.table import Table

from bham_events.config import AppConfig, OUTPUT_DIR, load_interests
from bham_events.email_sender import save_html_preview, send_review_email
from bham_events.gemini_curator import discover_and_curate_events
from bham_events.models import DigestPayload, EventItem, EventStore
from bham_events.proton_calendar import generate_proton_calendar_files
from bham_events.scrapers import scrape_all_birmingham_venues
from bham_events.ytmusic_sync import interactive_ytmusic_setup, sync_ytmusic_profile

import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console()


def _build_demo_digest() -> DigestPayload:
    """Provides a realistic Birmingham sample digest for `--demo` testing without an API key."""
    today = datetime.now()
    d1 = (today + timedelta(days=3)).strftime("%Y-%m-%d")
    d2 = (today + timedelta(days=6)).strftime("%Y-%m-%d")
    d3 = (today + timedelta(days=9)).strftime("%Y-%m-%d")
    d4 = (today + timedelta(days=12)).strftime("%Y-%m-%d")
    d5 = (today + timedelta(days=14)).strftime("%Y-%m-%d")

    return DigestPayload(
        headline="Birmingham Sound, Stage & Bite: Your Curated Week Ahead",
        intro_note=(
            "From soulful horns in Avondale and touring podcast comedians at the Stardome "
            "to local culinary pop-ups at Pepper Place and theater downtown, here are the best "
            "Birmingham events matched to your tastes."
        ),
        events=[
            EventItem(
                title="St. Paul & The Broken Bones (Homecoming Show)",
                category="music",
                venue="Avondale Brewing Company",
                start_date=d1,
                start_time="19:30",
                end_time="22:30",
                price_info="$42 - $65",
                url="https://www.avondalebrewing.com/calendar-tickets",
                description="Birmingham's powerhouse eight-piece soul band plays an outdoor evening set under the lights at Avondale Brewing.",
                match_reason="Matches your YouTube Music library & Birmingham soul/indie favorites",
                relevance_score=98,
                is_ytmusic_match=True,
            ),
            EventItem(
                title="Dusty Slay — The Night Shift Tour",
                category="comedy_podcast",
                venue="Alabama Theatre",
                start_date=d2,
                start_time="19:00",
                end_time="21:30",
                price_info="$39.50 - $79.50",
                url="https://alabamatheatre.com/events/",
                description="Southern stand-up comedian and Nateland podcast co-host Dusty Slay brings his signature dry observational humor to historic Alabama Theatre.",
                match_reason="Matches your podcast comedians list (Nateland / Theo Von / Nate Bargatze circle)",
                relevance_score=95,
                is_ytmusic_match=True,
            ),
            EventItem(
                title="Saturn Indie Showcase & Retro Sci-Fi Arcade Night",
                category="music",
                venue="Saturn Birmingham",
                start_date=d2,
                start_time="20:00",
                end_time="23:30",
                price_info="$18",
                url="https://saturnbirmingham.com/calendar/",
                description="High-energy touring indie rock double bill in Saturn's main room with free-play vintage consoles in Satellite Bar.",
                match_reason="Top Birmingham music venue match (Saturn)",
                relevance_score=90,
                is_ytmusic_match=False,
            ),
            EventItem(
                title="Pepper Place Fall Chef's Table & Night Market",
                category="food",
                venue="The Market at Pepper Place",
                start_date=d3,
                start_time="17:30",
                end_time="21:00",
                price_info="Free entry (tasting tickets $15+)",
                url="https://pepperplacemarket.com/",
                description="Local James Beard-recognized Birmingham chefs team up with Alabama farmers for seasonal small plates, craft cider, and live acoustic sets.",
                match_reason="Curated Birmingham food festival & culinary pop-up",
                relevance_score=89,
                is_ytmusic_match=False,
            ),
            EventItem(
                title="Red Mountain Theatre: Cabaret",
                category="theater_play",
                venue="Red Mountain Theatre Arts Campus",
                start_date=d4,
                start_time="19:30",
                end_time="22:00",
                price_info="$35 - $60",
                url="https://www.redmountaintheatre.org/season-tickets-shows/",
                description="An immersive downtown Birmingham production of Kander and Ebb's Tony-winning musical classic inside RMT's modern theatre space.",
                match_reason="Acclaimed local Birmingham theatre production",
                relevance_score=87,
                is_ytmusic_match=False,
            ),
            EventItem(
                title="Stardome Weekend Headliner Comedy Showcase",
                category="comedy_podcast",
                venue="Stardome Comedy Club (Hoover)",
                start_date=d5,
                start_time="19:30",
                end_time="21:30",
                price_info="$25",
                url="https://www.stardome.com/",
                description="Touring club headliner featured on Netflix and top comedy podcasts performs an intimate Friday night set.",
                match_reason="Birmingham's premier stand-up comedy club",
                relevance_score=84,
                is_ytmusic_match=False,
            ),
        ],
    )


def print_terminal_summary(digest: DigestPayload, master_ics: Path, html_path: Path) -> None:
    """Prints a rich summary table of discovered events to the terminal."""
    console.print(f"\n[bold magenta]{digest.headline}[/bold magenta]")
    console.print(f"[italic]{digest.intro_note}[/italic]\n")

    table = Table(title=f"Curated Birmingham Events ({len(digest.events)})", show_lines=True)
    table.add_column("Date & Time", style="cyan", no_wrap=True)
    table.add_column("Category", style="magenta")
    table.add_column("Event & Venue", style="bold white")
    table.add_column("Why It Matched", style="green")
    table.add_column("Price", style="yellow")

    for ev in digest.events:
        yt_star = " [YTM]" if ev.is_ytmusic_match else ""
        table.add_row(
            f"{ev.start_date}\n{ev.start_time}",
            f"{ev.category}{yt_star}",
            f"{ev.title}\n[dim]@ {ev.venue}[/dim]",
            f"{ev.match_reason} ({ev.relevance_score})",
            ev.price_info,
        )

    console.print(table)
    console.print(f"\n[bold green][OK] Master Proton Calendar (.ics):[/bold green] {master_ics}")
    console.print(f"[bold green][OK] Individual Event (.ics) folder:[/bold green] {master_ics.parent / 'ics'}")
    console.print(f"[bold green][OK] Interactive HTML Review Digest:[/bold green] {html_path}\n")


def serve_calendar_feed(port: int = 8765) -> None:
    """Serves ./output/ over HTTP so Proton Calendar or local browser can subscribe/view."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(OUTPUT_DIR), **kwargs)

    with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
        console.print(
            f"[bold green]Serving output directory at http://127.0.0.1:{port}/[/bold green]\n"
            f"  • Digest HTML: http://127.0.0.1:{port}/latest_digest.html\n"
            f"  • ICS Feed:    http://127.0.0.1:{port}/birmingham_events.ics\n"
            "Press Ctrl+C to stop."
        )
        httpd.serve_forever()


async def run_pipeline(args: argparse.Namespace) -> int:
    config = AppConfig()
    config.ensure_dirs()
    load_interests(config)

    if args.setup_ytmusic:
        interactive_ytmusic_setup(config)
        sync_ytmusic_profile(config)
        return 0

    if args.sync_ytmusic_only:
        sync_ytmusic_profile(config)
        return 0

    if args.serve_ics:
        serve_calendar_feed(port=args.port)
        return 0

    store = EventStore(config.seen_events_db)

    if args.demo:
        console.print("[bold yellow]Running in --demo mode with sample Birmingham events...[/bold yellow]")
        digest = _build_demo_digest()
    else:
        ytmusic_profile = sync_ytmusic_profile(config)
        scraped_context = await scrape_all_birmingham_venues()
        digest = discover_and_curate_events(config, scraped_context, ytmusic_profile)

    if args.new_only:
        filtered = [ev for ev in digest.events if not store.is_emailed(ev.uid)]
        if filtered:
            digest.events = filtered
        else:
            console.print("[yellow]No brand-new events since last emailed digest; keeping full list for calendar feed.[/yellow]")

    master_ics, individual_ics = generate_proton_calendar_files(config, digest.events)
    html_path = save_html_preview(config, digest)

    print_terminal_summary(digest, master_ics, html_path)

    emailed = False
    if not args.no_email:
        try:
            emailed = send_review_email(config, digest, master_ics, individual_ics)
        except Exception as exc:
            console.print(f"[bold red]SMTP Email error:[/bold red] {exc}")
            console.print("[dim]Check your Proton Mail Bridge / SMTP settings in .env.[/dim]")

    store.upsert_events(digest.events, mark_emailed=emailed)

    if args.open_browser:
        webbrowser.open(html_path.as_uri())

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Birmingham, AL Event Scraper & Proton Calendar Digest"
    )
    parser.add_argument(
        "--setup-ytmusic",
        action="store_true",
        help="Interactive wizard to authenticate YouTube Music (ytmusicapi)",
    )
    parser.add_argument(
        "--sync-ytmusic-only",
        action="store_true",
        help="Sync YouTube Music artists & podcasts into data/interests.json and exit",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Generate a sample Birmingham digest, HTML report, and Proton Calendar .ics files without calling Gemini",
    )
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Generate HTML preview and .ics files without sending an email via SMTP",
    )
    parser.add_argument(
        "--new-only",
        action="store_true",
        help="Filter out events that were already sent in a previous email digest",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the generated HTML review digest in your default browser",
    )
    parser.add_argument(
        "--serve-ics",
        action="store_true",
        help="Run a local HTTP server for output/latest_digest.html and output/birmingham_events.ics",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for --serve-ics (default: 8765)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    cli_args = parse_args()
    raise SystemExit(asyncio.run(run_pipeline(cli_args)))
