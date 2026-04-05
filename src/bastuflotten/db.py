"""Database layer — SQLite via aiosqlite."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite
from dotenv import load_dotenv

load_dotenv()

_FMT = "%Y-%m-%dT%H:%M:%S"


def _db_path() -> str:
    return os.getenv("DB_PATH", "/data/bookings.db")


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(_FMT)


def _end_time(start: str, duration_hours: float) -> str:
    dt = datetime.strptime(start, _FMT).replace(tzinfo=timezone.utc)
    return _utc(dt + timedelta(hours=duration_hours))


def _now() -> str:
    return _utc(datetime.now(timezone.utc))


async def init_db() -> None:
    Path(_db_path()).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS bookings (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                booked_by_id    TEXT    NOT NULL,
                booked_by_name  TEXT    NOT NULL,
                guest_name      TEXT,
                start_time      TEXT    NOT NULL,
                duration_hours  REAL    NOT NULL DEFAULT 4.0,
                open_invite     INTEGER NOT NULL DEFAULT 0,
                status          TEXT    NOT NULL DEFAULT 'active',
                created_at      TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cancellations (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id        INTEGER NOT NULL REFERENCES bookings(id),
                cancelled_by_id   TEXT    NOT NULL,
                cancelled_by_name TEXT    NOT NULL,
                reason            TEXT,
                cancelled_at      TEXT    NOT NULL
            );
        """)
        await db.commit()


async def create_booking(
    booked_by_id: str,
    booked_by_name: str,
    start_time: datetime,
    duration_hours: float,
    open_invite: bool,
    guest_name: str | None = None,
) -> int:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        cursor = await db.execute(
            """
            INSERT INTO bookings
                (booked_by_id, booked_by_name, guest_name, start_time,
                 duration_hours, open_invite, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?)
            """,
            (
                booked_by_id,
                booked_by_name,
                guest_name,
                _utc(start_time),
                duration_hours,
                int(open_invite),
                _now(),
            ),
        )
        await db.commit()
        return int(cursor.lastrowid or 0)


async def get_booking(booking_id: int) -> aiosqlite.Row | None:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
        return await cursor.fetchone()


async def get_upcoming_bookings(offset: int = 0, limit: int = 4) -> list:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        # Include bookings that haven't ended yet (start + duration > now)
        # We fetch all active bookings and filter in Python to avoid
        # SQLite float-modifier issues with duration_hours
        cursor = await db.execute(
            """
            SELECT * FROM bookings
            WHERE status = 'active'
            ORDER BY start_time ASC
            """,
        )
        all_rows = await cursor.fetchall()

    now = _now()
    upcoming = [
        row
        for row in all_rows
        if _end_time(row["start_time"], row["duration_hours"]) > now
    ]
    return upcoming[offset : offset + limit]


async def count_upcoming_bookings() -> int:
    async with aiosqlite.connect(_db_path()) as db:
        cursor = await db.execute(
            "SELECT start_time, duration_hours FROM bookings WHERE status = 'active'",
        )
        rows = await cursor.fetchall()
    now = _now()
    return sum(1 for row in rows if _end_time(row[0], row[1]) > now)


async def get_cancelled_bookings(offset: int = 0, limit: int = 10) -> list:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT b.*, c.cancelled_by_name, c.cancelled_at, c.reason
            FROM bookings b
            JOIN cancellations c ON c.booking_id = b.id
            WHERE b.status = 'cancelled'
            ORDER BY c.cancelled_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        return list(await cursor.fetchall())


async def has_conflict(
    start_time: datetime,
    duration_hours: float,
    exclude_id: int | None = None,
) -> bool:
    """Overlap check done in Python to avoid SQLite float-modifier issues."""
    new_start = _utc(start_time)
    new_end = _utc(start_time + timedelta(hours=duration_hours))
    async with aiosqlite.connect(_db_path()) as db:
        query = "SELECT id, start_time, duration_hours FROM bookings WHERE status = 'active'"
        params: list = []
        if exclude_id:
            query += " AND id != ?"
            params.append(exclude_id)
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
    for row in rows:
        ex_start = str(row[1])
        ex_end = _utc(
            datetime.strptime(ex_start, _FMT).replace(tzinfo=timezone.utc)
            + timedelta(hours=float(row[2]))
        )
        if new_start < ex_end and new_end > ex_start:
            return True
    return False


async def cancel_booking(
    booking_id: int,
    cancelled_by_id: str,
    cancelled_by_name: str,
    reason: str | None = None,
) -> bool:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        cursor = await db.execute(
            "SELECT status FROM bookings WHERE id = ?", (booking_id,)
        )
        row = await cursor.fetchone()
        if not row or str(row["status"]) != "active":
            return False
        await db.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,)
        )
        await db.execute(
            """
            INSERT INTO cancellations
                (booking_id, cancelled_by_id, cancelled_by_name, reason, cancelled_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (booking_id, cancelled_by_id, cancelled_by_name, reason, _now()),
        )
        await db.commit()
        return True
