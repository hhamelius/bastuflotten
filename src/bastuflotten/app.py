"""FastAPI + Slack Bolt entry point."""

import json
import logging
import os
import ssl
from contextlib import asynccontextmanager

import aiohttp
import certifi
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp

from . import commands
from .db import init_db

load_dotenv()

logging.basicConfig(level=logging.DEBUG)

# Fix SSL certificate verification on macOS with python.org Python installs
ssl_context = ssl.create_default_context(cafile=certifi.where())
connector = aiohttp.TCPConnector(ssl=ssl_context)
client_session = aiohttp.ClientSession(connector=connector)

bolt = AsyncApp(
    token=os.environ["SLACK_BOT_TOKEN"],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
)
bolt.client.session = client_session
commands.register(bolt)
handler = AsyncSlackRequestHandler(bolt)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await client_session.close()


app = FastAPI(title="Bastuflotten", lifespan=lifespan)


@app.post("/slack/events")
async def slack_events(req: Request) -> Response:
    # Log the raw payload so we can see what Slack is sending
    body = await req.body()
    try:
        parsed = json.loads(body)
        payload_type = parsed.get("type")
        callback_id = parsed.get("callback_id") or parsed.get("view", {}).get(
            "callback_id"
        )
        logging.info(f"Slack event: type={payload_type} callback_id={callback_id}")
    except Exception:
        try:
            from urllib.parse import parse_qs

            parsed_form = parse_qs(body.decode())
            payload_str = parsed_form.get("payload", [None])[0]
            if payload_str:
                payload = json.loads(payload_str)
                payload_type = payload.get("type")
                callback_id = payload.get("view", {}).get("callback_id")
                logging.info(
                    f"Slack event (form): type={payload_type} callback_id={callback_id}"
                )
        except Exception as e:
            logging.warning(f"Could not parse Slack payload: {e}")
    return await handler.handle(req)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
