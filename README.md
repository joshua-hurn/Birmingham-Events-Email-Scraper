# Birmingham, AL Event Curator & Proton Calendar Digest

Scrapes and curates upcoming **Birmingham, Alabama** events across:
- **🎵 Live Music & Concerts** (matched against your **YouTube Music** artists, subscriptions, and liked songs via `ytmusicapi`)
- **🎙️ Podcast Comedians & Stand-Up** (Stardome Comedy Club, Alabama Theatre, Lyric Theatre, BJCC, Saturn)
- **🍽️ Food Events, Pop-Ups & Festivals** (Pepper Place, culinary pop-ups, food/beer/wine festivals)
- **🎭 Plays, Broadway & Performing Arts** (Red Mountain Theatre, Virginia Samford Theatre, Terrific New Theatre, Broadway in Birmingham at BJCC, Alys Stephens Center)
- **✨ Fun & Unique Local Happenings** (Bham Now, InBirmingham, Saturn game/trivia nights, Railroad Park)

Generates RFC 5545 `.ics` calendar files (`America/Chicago` timezone) and sends a rich HTML review email with `.ics` attachments via **Proton Mail Bridge** so you can add events to **Proton Calendar** in one click (or subscribe to a live `.ics` URL).

---

## Quick Start

### 1. Configure `.env`
Copy `.env.example` to `.env` and fill in your Gemini API key and Proton Mail Bridge details:
```powershell
Copy-Item .env.example .env
```

- **`GEMINI_API_KEY`**: Get a key at [Google AI Studio](https://aistudio.google.com/apikey).
- **Proton Mail Bridge**: Open Proton Mail Bridge -> click your account -> **Mailbox details** -> copy the local SMTP host (`127.0.0.1`), port (`1025`), your Proton email address, and the **Bridge password** into `.env`.

### 2. Connect Your YouTube Music Account (`ytmusicapi`)
Run the interactive setup wizard once to pull your YouTube Music subscriptions, library artists, liked songs, and podcasts into `data/interests.json`:
```powershell
.\.venv\Scripts\python.exe main.py --setup-ytmusic
```
*(You can also manually edit `data/interests.json` at any time to add or remove favorite artists, podcast comedians, or venues.)*

### 3. Test in Demo Mode (No API Key Required)
Generate a sample HTML digest and Proton Calendar `.ics` files immediately:
```powershell
.\.venv\Scripts\python.exe main.py --demo --no-email --open-browser
```

### 4. Run the Full Live Scraper + Gemini Curator + Proton Email Digest
```powershell
.\.venv\Scripts\python.exe main.py
```
Useful flags:
- `--no-email`: Generate `output/latest_digest.html` and `output/birmingham_events.ics` without sending SMTP email.
- `--new-only`: Only include events that haven't been emailed in a previous run (tracked in `data/events.db`).
- `--open-browser`: Automatically open `output/latest_digest.html` in your browser.
- `--sync-ytmusic-only`: Re-sync `data/interests.json` from YouTube Music and exit.

---

## How to Add Events to Proton Calendar

You have **two seamless ways** to populate Proton Calendar:

### Option A: One-Click Import from Your Proton Mail Review Email (Selective)
Every digest email attaches:
1. **Individual `.ics` files** (`output/ics/<date>_<event>.ics`) for each event — click **"Add to Proton Calendar"** inside Proton Mail on only the events you want to attend.
2. **Master `birmingham_events.ics`** (`output/birmingham_events.ics`) — imports the entire batch at once.

### Option B: Live Subscribed Calendar Feed in Proton Calendar (Automatic)
If you push this repository to GitHub and add `GEMINI_API_KEY` to your repo Secrets, the included workflow (`.github/workflows/update_calendar_feed.yml`) automatically updates `output/birmingham_events.ics` every week.
1. Copy the raw GitHub URL for `output/birmingham_events.ics` (or a Gist raw URL).
2. In **Proton Calendar** web app -> left sidebar -> **Other calendars (+)** -> **Add calendar from URL** -> paste the URL.
3. Proton Calendar will automatically sync all curated Birmingham events into a toggleable **"Birmingham Curated Events"** layer!

---

## Schedule Weekly Runs on Windows

Run the included PowerShell script to register a weekly Windows Scheduled Task (defaults to every Thursday at 8:30 AM):
```powershell
.\schedule_windows_task.ps1 -RegisterTask -DayOfWeek Thursday -Time 08:30AM
```
