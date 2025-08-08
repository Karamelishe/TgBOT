from __future__ import annotations

import asyncio
import aiosqlite
from dataclasses import dataclass
from typing import Optional, List, Tuple
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager


@dataclass
class User:
    id: int
    tg_user_id: int
    chat_id: int
    full_name: str
    phone: Optional[str]
    is_admin: int
    created_at: str


@dataclass
class Slot:
    id: int
    slot_utc: str  # ISO format in UTC
    duration_minutes: int
    note: Optional[str]
    created_by: Optional[int]


@dataclass
class Booking:
    id: int
    user_id: int
    slot_id: int
    created_at: str
    reminder_sent: int
    status: str
    guests_count: int
    reminder_hours_before: Optional[int]
    reminder_enabled: int


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def connect(self) -> aiosqlite.Connection:
        conn = await aiosqlite.connect(self.db_path)
        await conn.execute("PRAGMA foreign_keys = ON;")
        await conn.execute("PRAGMA journal_mode = WAL;")
        await conn.execute("PRAGMA synchronous = NORMAL;")
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()

    async def init(self) -> None:
        async with self.connect() as conn:
            await conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tg_user_id INTEGER NOT NULL UNIQUE,
                    chat_id INTEGER NOT NULL,
                    full_name TEXT NOT NULL,
                    phone TEXT,
                    is_admin INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS slots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slot_utc TEXT NOT NULL, -- ISO 8601 in UTC
                    duration_minutes INTEGER NOT NULL DEFAULT 60,
                    note TEXT,
                    created_by INTEGER,
                    UNIQUE(slot_utc)
                );

                CREATE TABLE IF NOT EXISTS bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    slot_id INTEGER NOT NULL UNIQUE REFERENCES slots(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    reminder_sent INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'booked',
                    guests_count INTEGER NOT NULL DEFAULT 1,
                    reminder_hours_before INTEGER DEFAULT 2,
                    reminder_enabled INTEGER NOT NULL DEFAULT 1
                );
                """
            )
            await conn.commit()

    # Users
    async def upsert_user(self, tg_user_id: int, chat_id: int, full_name: str, is_admin: int) -> int:
        async with self.connect() as conn:
            await conn.execute(
                """
                INSERT INTO users (tg_user_id, chat_id, full_name, is_admin)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(tg_user_id) DO UPDATE SET chat_id=excluded.chat_id, full_name=excluded.full_name, is_admin=excluded.is_admin
                """,
                (tg_user_id, chat_id, full_name, is_admin),
            )
            await conn.commit()
            async with conn.execute("SELECT id FROM users WHERE tg_user_id = ?", (tg_user_id,)) as cur:
                row = await cur.fetchone()
                return int(row[0])

    async def set_user_phone(self, tg_user_id: int, phone: str) -> None:
        async with self.connect() as conn:
            await conn.execute("UPDATE users SET phone = ? WHERE tg_user_id = ?", (phone, tg_user_id))
            await conn.commit()

    async def get_user_by_tg(self, tg_user_id: int) -> Optional[User]:
        async with self.connect() as conn:
            async with conn.execute("SELECT * FROM users WHERE tg_user_id = ?", (tg_user_id,)) as cur:
                row = await cur.fetchone()
                if not row:
                    return None
                return User(**dict(row))

    # Slots
    async def add_slot(self, slot_utc_iso: str, duration_minutes: int = 60, note: Optional[str] = None, created_by: Optional[int] = None) -> int:
        async with self.connect() as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO slots (slot_utc, duration_minutes, note, created_by) VALUES (?, ?, ?, ?)",
                (slot_utc_iso, duration_minutes, note, created_by),
            )
            await conn.commit()
            async with conn.execute("SELECT id FROM slots WHERE slot_utc = ?", (slot_utc_iso,)) as cur:
                row = await cur.fetchone()
                return int(row[0])

    async def delete_slot(self, slot_id: int) -> int:
        async with self.connect() as conn:
            cur = await conn.execute("DELETE FROM slots WHERE id = ?", (slot_id,))
            await conn.commit()
            return cur.rowcount

    async def update_slot_note(self, slot_id: int, note: str) -> bool:
        async with self.connect() as conn:
            cur = await conn.execute("UPDATE slots SET note = ? WHERE id = ?", (note, slot_id))
            await conn.commit()
            return cur.rowcount > 0

    async def list_free_slots(self, since_utc_iso: Optional[str] = None, date_only: Optional[str] = None) -> List[Slot]:
        query = (
            "SELECT s.* FROM slots s "
            "LEFT JOIN bookings b ON b.slot_id = s.id "
            "WHERE b.id IS NULL"
        )
        params: List[str] = []
        if since_utc_iso:
            query += " AND s.slot_utc >= ?"
            params.append(since_utc_iso)
        if date_only:
            # date_only is YYYY-MM-DD in UTC day; we filter by day boundaries in UTC
            query += " AND s.slot_utc >= ? AND s.slot_utc < ?"
            start = f"{date_only}T00:00:00+00:00"
            end = f"{date_only}T23:59:59+00:00"
            params.extend([start, end])
        query += " ORDER BY s.slot_utc ASC"

        async with self.connect() as conn:
            async with conn.execute(query, params) as cur:
                rows = await cur.fetchall()
                return [Slot(**dict(r)) for r in rows]

    async def list_slots(self, date_only: Optional[str] = None) -> List[Slot]:
        query = "SELECT * FROM slots"
        params: List[str] = []
        if date_only:
            query += " WHERE slot_utc >= ? AND slot_utc < ?"
            start = f"{date_only}T00:00:00+00:00"
            end = f"{date_only}T23:59:59+00:00"
            params.extend([start, end])
        query += " ORDER BY slot_utc ASC"
        async with self.connect() as conn:
            async with conn.execute(query, params) as cur:
                rows = await cur.fetchall()
                return [Slot(**dict(r)) for r in rows]

    # Bookings
    async def create_booking(self, user_id: int, slot_id: int, guests_count: int = 1, reminder_hours_before: Optional[int] = 2, reminder_enabled: int = 1) -> int:
        async with self.connect() as conn:
            await conn.execute(
                "INSERT INTO bookings (user_id, slot_id, guests_count, reminder_hours_before, reminder_enabled) VALUES (?, ?, ?, ?, ?)",
                (user_id, slot_id, guests_count, reminder_hours_before, reminder_enabled),
            )
            await conn.commit()
            async with conn.execute("SELECT id FROM bookings WHERE user_id = ? AND slot_id = ?", (user_id, slot_id)) as cur:
                row = await cur.fetchone()
                return int(row[0])

    async def get_booking_with_user_and_slot(self, booking_id: int) -> Optional[Tuple[Booking, User, Slot]]:
        async with self.connect() as conn:
            async with conn.execute(
                """
                SELECT b.*, u.*, s.*
                FROM bookings b
                JOIN users u ON u.id = b.user_id
                JOIN slots s ON s.id = b.slot_id
                WHERE b.id = ?
                """,
                (booking_id,),
            ) as cur:
                row = await cur.fetchone()
                if not row:
                    return None
                # Row mapping when selecting * from multiple tables is messy; instead query separately when needed.
                return None

    async def list_bookings(self, date_only: Optional[str] = None) -> List[Tuple[Booking, User, Slot]]:
        query = (
            "SELECT b.id AS b_id, b.user_id AS b_user_id, b.slot_id AS b_slot_id, b.created_at AS b_created_at, b.reminder_sent AS b_reminder_sent, b.status AS b_status, b.guests_count AS b_guests_count, b.reminder_hours_before AS b_reminder_hours_before, b.reminder_enabled AS b_reminder_enabled, "
            "u.id AS u_id, u.tg_user_id AS u_tg_user_id, u.chat_id AS u_chat_id, u.full_name AS u_full_name, u.phone AS u_phone, u.is_admin AS u_is_admin, u.created_at AS u_created_at, "
            "s.id AS s_id, s.slot_utc AS s_slot_utc, s.duration_minutes AS s_duration_minutes, s.note AS s_note, s.created_by AS s_created_by "
            "FROM bookings b JOIN users u ON u.id = b.user_id JOIN slots s ON s.id = b.slot_id"
        )
        params: List[str] = []
        if date_only:
            query += " WHERE s.slot_utc >= ? AND s.slot_utc < ?"
            start = f"{date_only}T00:00:00+00:00"
            end = f"{date_only}T23:59:59+00:00"
            params.extend([start, end])
        query += " ORDER BY s.slot_utc ASC"
        async with self.connect() as conn:
            async with conn.execute(query, params) as cur:
                rows = await cur.fetchall()
                result: List[Tuple[Booking, User, Slot]] = []
                for r in rows:
                    booking = Booking(
                        id=r["b_id"],
                        user_id=r["b_user_id"],
                        slot_id=r["b_slot_id"],
                        created_at=r["b_created_at"],
                        reminder_sent=r["b_reminder_sent"],
                        status=r["b_status"],
                        guests_count=r["b_guests_count"],
                        reminder_hours_before=r["b_reminder_hours_before"],
                        reminder_enabled=r["b_reminder_enabled"],
                    )
                    user = User(
                        id=r["u_id"],
                        tg_user_id=r["u_tg_user_id"],
                        chat_id=r["u_chat_id"],
                        full_name=r["u_full_name"],
                        phone=r["u_phone"],
                        is_admin=r["u_is_admin"],
                        created_at=r["u_created_at"],
                    )
                    slot = Slot(
                        id=r["s_id"],
                        slot_utc=r["s_slot_utc"],
                        duration_minutes=r["s_duration_minutes"],
                        note=r["s_note"],
                        created_by=r["s_created_by"],
                    )
                    result.append((booking, user, slot))
                return result

    async def mark_reminder_sent(self, booking_id: int) -> None:
        async with self.connect() as conn:
            await conn.execute("UPDATE bookings SET reminder_sent = 1 WHERE id = ?", (booking_id,))
            await conn.commit()

    async def find_bookings_for_reminder(self, now_utc: datetime) -> List[Tuple[int, int, int, str, int]]:
        # Returns tuples: (booking_id, user_chat_id, slot_id, slot_utc_iso, reminder_hours_before)
        # window: send when slot_time - now in [reminder_hours_before, reminder_hours_before + 60s)
        # We need to check each booking's reminder settings
        query = (
            "SELECT b.id AS booking_id, u.chat_id AS chat_id, s.id AS slot_id, s.slot_utc AS slot_utc, b.reminder_hours_before AS reminder_hours_before "
            "FROM bookings b JOIN users u ON u.id = b.user_id JOIN slots s ON s.id = b.slot_id "
            "WHERE b.reminder_sent = 0 AND b.reminder_enabled = 1 AND b.status = 'booked'"
        )
        async with self.connect() as conn:
            async with conn.execute(query) as cur:
                rows = await cur.fetchall()
                result = []
                for r in rows:
                    reminder_hours = r["reminder_hours_before"] or 2  # default to 2 hours
                    lower = now_utc + timedelta(hours=reminder_hours)
                    upper = lower + timedelta(seconds=60)
                    slot_time = datetime.fromisoformat(r["slot_utc"].replace('Z', '+00:00'))
                    if lower <= slot_time < upper:
                        result.append((r["booking_id"], r["chat_id"], r["slot_id"], r["slot_utc"], reminder_hours))
                return result