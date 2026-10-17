"""YouTube Music integration via ytmusicapi to extract artists, liked songs, and podcasts."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from rich.console import Console
from ytmusicapi import YTMusic, setup

from .config import AppConfig, load_interests

console = Console()


def interactive_ytmusic_setup(config: AppConfig) -> Path:
    """Walks the user through setting up ytmusicapi browser headers."""
    config.ensure_dirs()
    console.print("\n[bold cyan]=== YouTube Music Authentication Setup ===[/bold cyan]")
    console.print(
        "To pull your YouTube Music subscriptions, library artists, liked songs, and podcasts,\n"
        "we use [bold]ytmusicapi[/bold] with your authenticated browser headers.\n\n"
        "[bold]Instructions:[/bold]\n"
        "1. Open [link=https://music.youtube.com]https://music.youtube.com[/link] in Chrome or Firefox while logged in.\n"
        "2. Press [bold]F12[/bold] (DevTools) -> go to the [bold]Network[/bold] tab.\n"
        "3. Filter by [bold]browse[/bold] and click anywhere on YouTube Music (e.g., Library).\n"
        "4. Right-click a `browse?...` POST request ->Copy -> Copy Request Headers (or Copy as cURL).\n"
    )
    setup(filepath=str(config.ytmusic_auth_file))
    console.print(f"[bold green]Saved YouTube Music credentials to {config.ytmusic_auth_file}[/bold green]")
    return config.ytmusic_auth_file


def sync_ytmusic_profile(config: AppConfig, max_artists: int = 120) -> dict[str, list[str]]:
    """
    Pulls artists, subscriptions, liked songs, and saved podcasts from YouTube Music,
    merges them into `data/interests.json`, and returns the synced lists.
    """
    interests = load_interests(config)

    if not config.ytmusic_auth_file.exists():
        console.print(
            f"[yellow]No YouTube Music auth file found at {config.ytmusic_auth_file}.[/yellow]\n"
            "Using artists & podcasts from [bold]data/interests.json[/bold]. "
            "Run `python main.py --setup-ytmusic` anytime to link your YouTube Music account."
        )
        return {
            "artists": interests.get("favorite_artists", []),
            "podcasts": interests.get("podcast_comedians", []),
        }

    console.print("[cyan]Syncing your YouTube Music library, subscriptions, liked songs & podcasts...[/cyan]")
    yt = YTMusic(str(config.ytmusic_auth_file))

    artist_counts: Counter[str] = Counter()
    podcasts: set[str] = set(interests.get("podcast_comedians", []))

    # 1. Library Subscriptions (highest signal)
    try:
        subs = yt.get_library_subscriptions(limit=250) or []
        for item in subs:
            name = (item.get("artist") or "").strip()
            if name:
                artist_counts[name] += 10
    except Exception as exc:
        console.print(f"[dim]Warning: Could not fetch library subscriptions: {exc}[/dim]")

    # 2. Library Artists
    try:
        lib_artists = yt.get_library_artists(limit=250) or []
        for item in lib_artists:
            name = (item.get("artist") or "").strip()
            if name:
                artist_counts[name] += int(item.get("songs", 3) or 3) + 5
    except Exception as exc:
        console.print(f"[dim]Warning: Could not fetch library artists: {exc}[/dim]")

    # 3. Liked Songs
    try:
        liked = yt.get_liked_songs(limit=300) or {}
        for track in liked.get("tracks", []):
            for art in track.get("artists") or []:
                name = (art.get("name") or "").strip()
                if name and name.lower() not in ("various artists",):
                    artist_counts[name] += 2
    except Exception as exc:
        console.print(f"[dim]Warning: Could not fetch liked songs: {exc}[/dim]")

    # 4. Library Podcasts / Channels
    try:
        lib_podcasts = yt.get_library_podcasts(limit=100) or []
        for pod in lib_podcasts:
            title = (pod.get("title") or "").strip()
            channel_name = ""
            if isinstance(pod.get("channel"), dict):
                channel_name = (pod["channel"].get("name") or "").strip()
            if title and title.lower() not in ("new episodes", "episodes for later"):
                podcasts.add(title)
            if channel_name:
                podcasts.add(channel_name)
    except Exception as exc:
        console.print(f"[dim]Warning: Could not fetch library podcasts: {exc}[/dim]")

    # Merge with existing manual favorite_artists
    for existing in interests.get("favorite_artists", []):
        if existing.strip():
            artist_counts[existing.strip()] += 15

    top_artists = [name for name, _ in artist_counts.most_common(max_artists)]
    podcast_list = sorted(podcasts)

    interests["favorite_artists"] = top_artists
    interests["podcast_comedians"] = podcast_list
    config.interests_file.write_text(json.dumps(interests, indent=2), encoding="utf-8")

    console.print(
        f"[green]Synced {len(top_artists)} artists and {len(podcast_list)} podcasts/comedians "
        f"into {config.interests_file.name}.[/green]"
    )
    return {
        "artists": top_artists,
        "podcasts": podcast_list,
    }
