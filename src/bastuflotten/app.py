"""FastAPI + Slack Bolt entry point."""

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

# Use certifi certificates on all platforms for consistent SSL behaviour
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
    return await handler.handle(req)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
