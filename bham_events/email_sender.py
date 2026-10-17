"""HTML Email Builder and Proton Mail Bridge / SMTP sender."""

from __future__ import annotations

import base64
import html
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote
from rich.console import Console

from .config import AppConfig, OUTPUT_DIR
from .models import DigestPayload, EventItem
from .proton_calendar import build_ical_event
from icalendar import Calendar

console = Console()

CATEGORY_META = {
    "music": ("🎵 Live Music & YouTube Music Matches", "#6d4aff"),
    "comedy_podcast": ("🎙️ Podcast Comedians & Stand-Up", "#d97706"),
    "food": ("🍽️ Food Festivals, Pop-Ups & Drink", "#059669"),
    "theater_play": ("🎭 Plays, Broadway & Performing Arts", "#db2777"),
    "fun_local": ("✨ Fun & Unique Around Birmingham", "#2563eb"),
}


def _single_event_data_uri(item: EventItem) -> str:
    """Creates a data:text/calendar;base64 URI for local browser HTML preview."""
    cal = Calendar()
    cal.add("prodid", "-//Birmingham Event Curator//brave-fermi//EN")
    cal.add("version", "2.0")
    cal.add("method", "PUBLISH")
    cal.add_component(build_ical_event(item))
    b64 = base64.b64encode(cal.to_ical()).decode("ascii")
    return f"data:text/calendar;charset=utf-8;base64,{b64}"


def render_digest_html(
    config: AppConfig,
    digest: DigestPayload,
    for_browser_preview: bool = False,
) -> str:
    """Renders a sleek, Proton-themed responsive HTML review digest."""
    grouped: dict[str, list[EventItem]] = {k: [] for k in CATEGORY_META}
    for ev in digest.events:
        grouped.setdefault(ev.category, []).append(ev)

    feed_banner = ""
    if config.calendar_feed_url:
        safe_feed = html.escape(config.calendar_feed_url)
        feed_banner = f"""
        <div style="background:#f5f3ff;border:1px solid #ddd6fe;border-radius:10px;padding:14px 18px;margin-bottom:24px;">
          <div style="font-weight:700;color:#4c1d95;margin-bottom:4px;">📅 Proton Calendar Live Feed</div>
          <div style="font-size:13px;color:#4b5563;">
            Subscribed URL: <a href="{safe_feed}" style="color:#6d4aff;word-break:break-all;">{safe_feed}</a>
          </div>
        </div>
        """
    else:
        feed_banner = """
        <div style="background:#f5f3ff;border:1px solid #ddd6fe;border-radius:10px;padding:14px 18px;margin-bottom:24px;">
          <div style="font-weight:700;color:#4c1d95;margin-bottom:4px;">📅 Ready for Proton Calendar</div>
          <div style="font-size:13px;color:#4b5563;">
            In Proton Mail, click any attached <code>.ics</code> file on this email to add that event (or <code>birmingham_events.ics</code> for all events) directly to <strong>Proton Calendar</strong> in one click.
          </div>
        </div>
        """

    sections_html: list[str] = []
    for cat_key, (cat_title, accent_color) in CATEGORY_META.items():
        items = grouped.get(cat_key, [])
        if not items:
            continue

        cards_html: list[str] = []
        for idx, ev in enumerate(items, start=1):
            yt_badge = (
                '<span style="background:#fef3c7;color:#92400e;font-size:11px;font-weight:700;'
                'padding:3px 8px;border-radius:999px;margin-left:8px;vertical-align:middle;">'
                "★ YouTube Music Match</span>"
                if ev.is_ytmusic_match
                else ""
            )

            ticket_btn = ""
            if ev.url:
                safe_url = html.escape(ev.url)
                ticket_btn = (
                    f'<a href="{safe_url}" target="_blank" rel="noopener" '
                    f'style="display:inline-block;background:{accent_color};color:#ffffff;'
                    f'text-decoration:none;font-size:13px;font-weight:600;padding:7px 14px;'
                    f'border-radius:6px;margin-right:8px;">Tickets &amp; Info ↗</a>'
                )

            ics_btn = ""
            if for_browser_preview:
                data_uri = _single_event_data_uri(ev)
                ics_btn = (
                    f'<a href="{data_uri}" download="{html.escape(ev.slug)}.ics" '
                    f'style="display:inline-block;background:#f3f4f6;color:#1f2937;border:1px solid #d1d5db;'
                    f'text-decoration:none;font-size:13px;font-weight:600;padding:6px 12px;'
                    f'border-radius:6px;">+ Download .ics for Proton Calendar</a>'
                )
            else:
                ics_btn = (
                    f'<span style="display:inline-block;background:#f3f4f6;color:#374151;'
                    f'font-size:12px;padding:6px 10px;border-radius:6px;">'
                    f"📎 Attached: <code>{html.escape(ev.slug)}.ics</code></span>"
                )

            cards_html.append(
                f"""
                <div style="border:1px solid #e5e7eb;border-left:4px solid {accent_color};border-radius:8px;padding:16px;margin-bottom:14px;background:#ffffff;">
                  <div style="font-size:17px;font-weight:700;color:#111827;margin-bottom:4px;">
                    {html.escape(ev.title)}{yt_badge}
                  </div>
                  <div style="font-size:13px;color:#4b5563;margin-bottom:8px;">
                    📍 <strong>{html.escape(ev.venue)}</strong> &nbsp;|&nbsp;
                    🗓️ <strong>{html.escape(ev.start_date)}</strong> at {html.escape(ev.start_time)} &nbsp;|&nbsp;
                    🎟️ {html.escape(ev.price_info)}
                  </div>
                  <div style="font-size:14px;color:#1f2937;line-height:1.5;margin-bottom:10px;">
                    {html.escape(ev.description)}
                  </div>
                  <div style="font-size:12px;color:#6d4aff;background:#f5f3ff;padding:6px 10px;border-radius:6px;margin-bottom:12px;">
                    <strong>Why we picked this:</strong> {html.escape(ev.match_reason)} (Score: {ev.relevance_score}/100)
                  </div>
                  <div>
                    {ticket_btn}
                    {ics_btn}
                  </div>
                </div>
                """
            )

        sections_html.append(
            f"""
            <div style="margin-bottom:28px;">
              <h2 style="font-size:19px;color:{accent_color};border-bottom:2px solid {accent_color};padding-bottom:6px;margin-bottom:14px;">
                {cat_title} ({len(items)})
              </h2>
              {''.join(cards_html)}
            </div>
            """
        )

    generated_date = datetime.now().strftime("%B %d, %Y")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(digest.headline)}</title>
</head>
<body style="margin:0;padding:24px 12px;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#111827;">
  <div style="max-width:680px;margin:0 auto;background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 4px 16px rgba(0,0,0,0.06);">
    <div style="background:linear-gradient(135deg,#1b1340 0%,#6d4aff 100%);color:#ffffff;padding:28px 24px;">
      <div style="font-size:12px;text-transform:uppercase;letter-spacing:1.2px;opacity:0.85;margin-bottom:6px;">
        Birmingham, AL Cultural &amp; Music Digest • {generated_date}
      </div>
      <h1 style="margin:0 0 10px 0;font-size:24px;line-height:1.25;">{html.escape(digest.headline)}</h1>
      <p style="margin:0;font-size:14px;line-height:1.5;opacity:0.92;">{html.escape(digest.intro_note)}</p>
    </div>
    <div style="padding:24px;">
      {feed_banner}
      {''.join(sections_html)}
    </div>
    <div style="background:#f9fafb;border-top:1px solid #e5e7eb;padding:16px 24px;font-size:12px;color:#6b7280;text-align:center;">
      Curated for Birmingham, AL using YouTube Music + Gemini 3.8 Flash + Proton Calendar (.ics)
    </div>
  </div>
</body>
</html>
"""


def save_html_preview(config: AppConfig, digest: DigestPayload) -> Path:
    """Saves a standalone interactive HTML digest to `output/latest_digest.html`."""
    config.ensure_dirs()
    html_str = render_digest_html(config, digest, for_browser_preview=True)
    out_path = OUTPUT_DIR / "latest_digest.html"
    out_path.write_text(html_str, encoding="utf-8")
    return out_path


def send_review_email(
    config: AppConfig,
    digest: DigestPayload,
    master_ics: Path,
    individual_ics: list[tuple[EventItem, Path]],
) -> bool:
    """
    Sends the HTML digest email with `.ics` attachments via Proton Mail Bridge
    (127.0.0.1:1025) or custom SMTP.
    """
    smtp_cfg = config.smtp
    if not smtp_cfg.sender_email or not smtp_cfg.recipient_email:
        console.print(
            "[yellow]EMAIL_FROM or EMAIL_TO not configured in .env — skipping SMTP send. "
            "Your HTML digest and Proton Calendar .ics files are ready in ./output/![/yellow]"
        )
        return False

    msg = EmailMessage()
    msg["Subject"] = f"🎟️ Birmingham Events Digest: {digest.headline}"
    msg["From"] = smtp_cfg.sender_email
    msg["To"] = smtp_cfg.recipient_email

    # Plain-text fallback
    plain_lines = [
        digest.headline,
        "=" * len(digest.headline),
        digest.intro_note,
        "",
    ]
    for ev in digest.events:
        plain_lines.append(
            f"- [{ev.category.upper()}] {ev.title} @ {ev.venue} ({ev.start_date} {ev.start_time}) | {ev.price_info}"
        )
        plain_lines.append(f"  Why: {ev.match_reason}")
        if ev.url:
            plain_lines.append(f"  Link: {ev.url}")
        plain_lines.append("")

    msg.set_content("\n".join(plain_lines))
    html_body = render_digest_html(config, digest, for_browser_preview=False)
    msg.add_alternative(html_body, subtype="html")

    # Attach master .ics file
    msg.add_attachment(
        master_ics.read_bytes(),
        maintype="text",
        subtype="calendar",
        filename=master_ics.name,
        params={"method": "PUBLISH", "charset": "UTF-8"},
    )

    # Attach individual event .ics files so the user can import single events in Proton Mail
    for _, ics_path in individual_ics:
        msg.add_attachment(
            ics_path.read_bytes(),
            maintype="text",
            subtype="calendar",
            filename=ics_path.name,
            params={"method": "PUBLISH", "charset": "UTF-8"},
        )

    # SSL context (Proton Mail Bridge uses a local self-signed cert on 127.0.0.1:1025 by default)
    ssl_ctx = ssl.create_default_context()
    if not smtp_cfg.verify_cert:
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

    console.print(
        f"[cyan]Sending review email to {smtp_cfg.recipient_email} via "
        f"{smtp_cfg.host}:{smtp_cfg.port}...[/cyan]"
    )
    if smtp_cfg.use_ssl:
        with smtplib.SMTP_SSL(smtp_cfg.host, smtp_cfg.port, context=ssl_ctx, timeout=20) as server:
            if smtp_cfg.username and smtp_cfg.password:
                server.login(smtp_cfg.username, smtp_cfg.password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(smtp_cfg.host, smtp_cfg.port, timeout=20) as server:
            server.ehlo()
            if smtp_cfg.use_starttls:
                server.starttls(context=ssl_ctx)
                server.ehlo()
            if smtp_cfg.username and smtp_cfg.password:
                server.login(smtp_cfg.username, smtp_cfg.password)
            server.send_message(msg)

    console.print("[bold green][OK] Review email sent with Proton Calendar .ics attachments![/bold green]")
    return True
