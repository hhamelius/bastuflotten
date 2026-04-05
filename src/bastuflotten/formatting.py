"""Shared message formatting helpers."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import aiosqlite

STOCKHOLM = ZoneInfo("Europe/Stockholm")

SWEDISH_DAYS = ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"]
SWEDISH_MONTHS = [
    "", "januari", "februari", "mars", "april", "maj", "juni",
    "juli", "augusti", "september", "oktober", "november", "december",
]


def fmt_datetime(iso: str) -> str:
    """Format a stored UTC string as Swedish local time, DST-aware."""
    dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    local = dt.astimezone(STOCKHOLM)
    day_name = SWEDISH_DAYS[local.weekday()]
    month_name = SWEDISH_MONTHS[local.month]
    return f"{day_name} {local.day} {month_name} {local.year} kl. {local.strftime('%H:%M')}"


def fmt_duration(hours: float) -> str:
    if hours == int(hours):
        h = int(hours)
        return f"{h} timme" if h == 1 else f"{h} timmar"
    return f"{hours:.1f} timmar"


def booking_block(row: aiosqlite.Row, index: int | None = None) -> list[dict]:
    prefix = f"*#{row['id']}*" if index is None else f"*{index}. #{row['id']}*"
    guest = row["guest_name"] or "—"
    open_tag = "  🌊 _Öppen för alla_" if row["open_invite"] else ""
    duration = fmt_duration(row["duration_hours"])
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{prefix}{open_tag}\n"
                    f"📅  {fmt_datetime(row['start_time'])}  ·  {duration}\n"
                    f"👤  *Gäst:* {guest}\n"
                    f"🙋  *Bokad av:* {row['booked_by_name']}"
                ),
            },
        },
        {"type": "divider"},
    ]


def cancelled_booking_block(row: aiosqlite.Row) -> list[dict]:
    guest = row["guest_name"] or "—"
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"~*#{row['id']}*  {fmt_datetime(row['start_time'])}~\n"
                    f"👤  *Gäst:* {guest}  ·  *Bokad av:* {row['booked_by_name']}\n"
                    f"❌  *Avbokad av:* {row['cancelled_by_name']}  "
                    f"({fmt_datetime(row['cancelled_at'])})"
                    + (f"\n💬  _{row['reason']}_" if row["reason"] else "")
                ),
            },
        },
        {"type": "divider"},
    ]


def open_invite_announcement(row: aiosqlite.Row) -> list[dict]:
    duration = fmt_duration(row["duration_hours"])
    guest = row["guest_name"] or row["booked_by_name"]
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🛁 Bastuflotten är öppen för alla!"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{row['booked_by_name']}* har bokat Bastuflotten och bjuder in alla!\n\n"
                    f"📅  {fmt_datetime(row['start_time'])}  ·  {duration}\n"
                    f"👤  *Ansvarig:* {guest}\n\n"
                    f"_Hör av dig till {row['booked_by_name']} om du vill hänga med!_"
                ),
            },
        },
    ]
