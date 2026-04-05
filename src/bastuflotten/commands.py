"""Slash command and modal submission handlers."""

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from slack_bolt.async_app import AsyncApp

from .db import (
    cancel_booking,
    count_upcoming_bookings,
    create_booking,
    get_booking,
    get_cancelled_bookings,
    get_upcoming_bookings,
    has_conflict,
)
from .formatting import (
    booking_block,
    cancelled_booking_block,
    fmt_datetime,
    fmt_duration,
    open_invite_announcement,
)
from .modals import BOOKING_CALLBACK_ID, CANCEL_CALLBACK_ID, booking_modal, cancel_modal

load_dotenv()

STOCKHOLM = ZoneInfo("Europe/Stockholm")
CHANNEL = "bastuflotten"

# Command prefix: "/" in production, "/dev-" in local dev.
# Set SLACK_COMMAND_PREFIX in your .env, e.g. SLACK_COMMAND_PREFIX=/dev-
_PREFIX = os.getenv("SLACK_COMMAND_PREFIX", "/")


def _cmd(name: str) -> str:
    """Return the full command string for a given base name."""
    return f"{_PREFIX}{name}"


def register(app: AsyncApp) -> None:

    @app.command(_cmd("boka"))
    @app.command(_cmd("book"))
    async def cmd_boka(ack, body, client):
        await ack()
        await client.views_open(trigger_id=body["trigger_id"], view=booking_modal())

    @app.view(BOOKING_CALLBACK_ID)
    async def handle_booking_submit(ack, body, client, view):
        values = view["state"]["values"]
        user_id = body["user"]["id"]
        user_name = body["user"]["name"]

        date_str = values["date_block"]["date_value"]["selected_date"]
        time_str = (values["time_block"]["time_value"].get("value") or "").strip()
        duration_raw = values["duration_block"]["duration_value"]["value"].strip()
        guest_name = (
            values["guest_block"]["guest_value"].get("value") or ""
        ).strip() or None
        open_options = values["open_invite_block"]["open_invite_value"].get(
            "selected_options", []
        )
        open_invite = any(o["value"] == "open" for o in open_options)

        try:
            duration = float(duration_raw)
            if duration <= 0 or duration > 24:
                raise ValueError
        except ValueError:
            await ack(
                response_action="errors",
                errors={
                    "duration_block": "Ange ett tal mellan 0 och 24, t.ex. 4 eller 2.5"
                },
            )
            return

        import re

        if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", time_str):
            await ack(
                response_action="errors",
                errors={
                    "time_block": "Ange tid i formatet HH:MM, t.ex. 09:00 eller 14:30"
                },
            )
            return
        try:
            local_dt = datetime.fromisoformat(f"{date_str}T{time_str}:00")
            start_utc = local_dt.replace(tzinfo=STOCKHOLM).astimezone(timezone.utc)
        except ValueError:
            await ack(
                response_action="errors",
                errors={"date_block": "Ogiltigt datum eller tid"},
            )
            return

        if await has_conflict(start_utc, duration):
            await ack(
                response_action="errors",
                errors={"date_block": "Bastuflotten är redan bokad under den tiden"},
            )
            return

        await ack()
        booking_id = await create_booking(
            booked_by_id=user_id,
            booked_by_name=user_name,
            start_time=start_utc,
            duration_hours=duration,
            open_invite=open_invite,
            guest_name=guest_name,
        )
        row = await get_booking(booking_id)
        guest_label = guest_name or "dig"
        start_str = fmt_datetime(row["start_time"]) if row else "?"
        await client.chat_postMessage(
            channel=user_id,
            text=(
                f"✅ *Bokning #{booking_id} bekräftad!*\n"
                f"📅  {start_str}  ·  {fmt_duration(duration)}\n"
                f"👤  Bokad för: {guest_label}"
            ),
        )
        if open_invite and row:
            await client.chat_postMessage(
                channel=CHANNEL,
                text=f"🛁 {user_name} har bokat Bastuflotten och bjuder in alla!",
                blocks=open_invite_announcement(row),
            )

    @app.command(_cmd("avboka"))
    @app.command(_cmd("cancel"))
    async def cmd_avboka(ack, body, client, respond):
        await ack()
        text = (body.get("text") or "").strip()
        if not text.isdigit():
            await respond(
                text=f"Ange boknings-ID, t.ex. `{_cmd('avboka')} 3`",
                response_type="ephemeral",
            )
            return
        booking_id = int(text)
        row = await get_booking(booking_id)
        if not row:
            await respond(
                text=f"❌ Ingen bokning med ID #{booking_id} hittades.",
                response_type="ephemeral",
            )
            return
        if row["status"] == "cancelled":
            await respond(
                text=f"⚠️ Bokning #{booking_id} är redan avbokad.",
                response_type="ephemeral",
            )
            return
        if not row:
            await respond(
                text=f"❌ Ingen bokning med ID #{booking_id} hittades.",
                response_type="ephemeral",
            )
            return
        summary = (
            f"*#{row['id']}*  {fmt_datetime(row['start_time'])}  ·  "
            f"{fmt_duration(row['duration_hours'])}\nBokad av: {row['booked_by_name']}"
        )
        await client.views_open(
            trigger_id=body["trigger_id"], view=cancel_modal(booking_id, summary)
        )

    @app.view(CANCEL_CALLBACK_ID)
    async def handle_cancel_submit(ack, body, client, view):
        await ack()
        user_id = body["user"]["id"]
        user_name = body["user"]["name"]
        booking_id = int(view["private_metadata"])
        reason = (
            view["state"]["values"]["reason_block"]["reason_value"].get("value") or ""
        ).strip() or None

        success = await cancel_booking(
            booking_id=booking_id,
            cancelled_by_id=user_id,
            cancelled_by_name=user_name,
            reason=reason,
        )
        if success:
            row = await get_booking(booking_id)
            msg = f"❌ *Bokning #{booking_id} avbokad.*\nAvbokad av: {user_name}" + (
                f"\nAnledning: _{reason}_" if reason else ""
            )
            if row and row["booked_by_id"] != user_id:
                await client.chat_postMessage(
                    channel=row["booked_by_id"],
                    text=f"⚠️ Din bokning #{booking_id} ({fmt_datetime(row['start_time'])}) har avbokats av {user_name}.",
                )
            await client.chat_postMessage(channel=user_id, text=msg)
        else:
            await client.chat_postMessage(
                channel=user_id,
                text=f"❌ Det gick inte att avboka #{booking_id}.",
            )

    @app.command(_cmd("lista"))
    @app.command(_cmd("list"))
    async def cmd_lista(ack, body, respond):
        await ack()
        text = (body.get("text") or "").strip()
        offset = max(0, int(text)) if text.isdigit() else 0
        rows = await get_upcoming_bookings(offset=offset, limit=4)
        total = await count_upcoming_bookings()
        if not rows:
            await respond(
                text="Inga kommande bokningar."
                if offset == 0
                else "Inga fler bokningar.",
                response_type="ephemeral",
            )
            return
        blocks: list[dict] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🛁 Bastuflotten — kommande bokningar",
                },
            }
        ]
        for i, row in enumerate(rows, start=offset + 1):
            blocks.extend(booking_block(row, index=i))
        nav_parts = []
        if offset > 0:
            nav_parts.append(
                f"◀  `{_cmd('lista')} {max(0, offset - 4)}`  för föregående"
            )
        if offset + 4 < total:
            nav_parts.append(f"`{_cmd('lista')} {offset + 4}`  för nästa  ▶")
        if nav_parts:
            blocks.append(
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": "  ·  ".join(nav_parts)}],
                }
            )
        await respond(blocks=blocks, response_type="ephemeral")

    @app.command(_cmd("lista-avbokade"))
    @app.command(_cmd("cancelled"))
    async def cmd_lista_avbokade(ack, respond):
        await ack()
        rows = await get_cancelled_bookings(limit=10)
        if not rows:
            await respond(text="Inga avbokade bokningar.", response_type="ephemeral")
            return
        blocks: list[dict] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "❌ Bastuflotten — avbokade bokningar",
                },
            }
        ]
        for row in rows:
            blocks.extend(cancelled_booking_block(row))
        await respond(blocks=blocks, response_type="ephemeral")
