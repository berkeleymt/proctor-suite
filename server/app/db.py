"""Postgres persistence (invariant 5: commit here BEFORE touching memory or broadcasting).

Only the server process uses this, at startup (load) and on admin/proctor writes.
Room devices never cause a read: reads come from the in-memory Store (invariant 1).
Schema is owned by Alembic (alembic/), run by deploy.sh, never here (invariant 10).
"""

import asyncpg


async def connect(url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(url, min_size=1, max_size=4, command_timeout=10)


async def load_rooms(pool: asyncpg.Pool) -> tuple[list[asyncpg.Record], list[asyncpg.Record]]:
    async with pool.acquire() as c:
        rooms = await c.fetch("SELECT * FROM rooms ORDER BY name")
        cmds = await c.fetch("SELECT * FROM commands ORDER BY seq")
    return rooms, cmds


async def insert_room(pool: asyncpg.Pool, r) -> None:
    async with pool.acquire() as c:
        await c.execute(
            "INSERT INTO rooms (room_id, name, test_name, duration_ms, created_at_ms, version,"
            " session_seq, session_created_ms, deleted, doc_url)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) ON CONFLICT DO NOTHING",
            r.room_id, r.name, r.test_name, r.duration_ms, r.created_at_ms, r.version,
            r.session_seq, r.session_created_ms, r.deleted, r.doc_url,
        )  # fmt: skip


async def save_room(pool: asyncpg.Pool, r, audit: dict | None = None) -> None:
    """Write every editable field of a room, plus an optional audit row, in one transaction."""
    async with pool.acquire() as c, c.transaction():
        await c.execute(
            "UPDATE rooms SET name=$2, test_name=$3, duration_ms=$4, doc_url=$5, deleted=$6,"
            " session_seq=$7, session_created_ms=$8, version=$9 WHERE room_id=$1",
            r.room_id, r.name, r.test_name, r.duration_ms, r.doc_url, r.deleted,
            r.session_seq, r.session_created_ms, r.version,
        )  # fmt: skip
        if audit:
            await _insert_command(c, audit)


async def _insert_command(c, row: dict) -> None:
    await c.execute(
        "INSERT INTO commands (command_id, room_id, type, session_id, actor_kind,"
        " claimed_at_ms, received_at_ms, delta_ms, is_event, outcome, reason)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) ON CONFLICT (command_id) DO NOTHING",
        row["command_id"], row["room_id"], row["type"], row["session_id"],
        row["actor_kind"], row["claimed_at_ms"], row["received_at_ms"], row["delta_ms"],
        row["is_event"], row["outcome"], row["reason"],
    )  # fmt: skip


async def save_command(pool: asyncpg.Pool, row: dict, version: int) -> None:
    """One transaction: the command row and the room's new version."""
    async with pool.acquire() as c, c.transaction():
        await _insert_command(c, row)
        await c.execute("UPDATE rooms SET version=$2 WHERE room_id=$1", row["room_id"], version)
