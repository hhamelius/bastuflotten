"""Slack modal view definitions."""

import os
from datetime import date

from dotenv import load_dotenv

load_dotenv()

# Use a short env-specific identifier in callback IDs so dev and prod
# modals don't collide if both apps share the same workspace.
_ENV = "dev" if os.getenv("SLACK_COMMAND_PREFIX", "/").startswith("/dev") else "prod"
BOOKING_CALLBACK_ID = f"booking_modal_submit_{_ENV}"
CANCEL_CALLBACK_ID = f"cancel_modal_submit_{_ENV}"


def booking_modal() -> dict:
    today = date.today().isoformat()
    return {
        "type": "modal",
        "callback_id": BOOKING_CALLBACK_ID,
        "title": {"type": "plain_text", "text": "Boka Bastuflotten"},
        "submit": {"type": "plain_text", "text": "Boka"},
        "close": {"type": "plain_text", "text": "Avbryt"},
        "blocks": [
            {
                "type": "input",
                "block_id": "date_block",
                "label": {"type": "plain_text", "text": "Datum"},
                "element": {
                    "type": "datepicker",
                    "action_id": "date_value",
                    "initial_date": today,
                    "placeholder": {"type": "plain_text", "text": "Välj datum"},
                },
            },
            {
                "type": "input",
                "block_id": "time_block",
                "label": {"type": "plain_text", "text": "Starttid (HH:MM)"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "time_value",
                    "initial_value": "10:00",
                    "placeholder": {"type": "plain_text", "text": "t.ex. 14:30"},
                },
                "hint": {
                    "type": "plain_text",
                    "text": "Ange tid i 24-timmarsformat, t.ex. 09:00 eller 14:30",
                },
            },
            {
                "type": "input",
                "block_id": "duration_block",
                "label": {"type": "plain_text", "text": "Antal timmar (standard: 4)"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "duration_value",
                    "initial_value": "4",
                    "placeholder": {"type": "plain_text", "text": "t.ex. 2 eller 3.5"},
                },
                "hint": {
                    "type": "plain_text",
                    "text": "Ange antal timmar, t.ex. 4 eller 2.5",
                },
            },
            {
                "type": "input",
                "block_id": "guest_block",
                "optional": True,
                "label": {"type": "plain_text", "text": "Gästens namn (valfritt)"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "guest_value",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Du kan lämna det tomt om det är du som badar",
                    },
                },
            },
            {
                "type": "input",
                "block_id": "open_invite_block",
                "optional": True,
                "label": {"type": "plain_text", "text": "Öppen bokning"},
                "element": {
                    "type": "checkboxes",
                    "action_id": "open_invite_value",
                    "options": [
                        {
                            "text": {
                                "type": "mrkdwn",
                                "text": "*Öppen för alla att hänga med*",
                            },
                            "value": "open",
                        }
                    ],
                },
            },
        ],
    }


def cancel_modal(booking_id: int, booking_summary: str) -> dict:
    return {
        "type": "modal",
        "callback_id": CANCEL_CALLBACK_ID,
        "private_metadata": str(booking_id),
        "title": {"type": "plain_text", "text": "Avboka"},
        "submit": {"type": "plain_text", "text": "Avboka"},
        "close": {"type": "plain_text", "text": "Avbryt"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Du är på väg att avboka:\n\n{booking_summary}",
                },
            },
            {
                "type": "input",
                "block_id": "reason_block",
                "optional": True,
                "label": {"type": "plain_text", "text": "Anledning (valfritt)"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "reason_value",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "t.ex. planer ändrades",
                    },
                },
            },
        ],
    }
