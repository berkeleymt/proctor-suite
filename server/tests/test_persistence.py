"""Real-Postgres tests. Skipped unless TEST_DATABASE_URL is set (CI sets it; see ci.yml).

They run the real Alembic migration, then check that a "restart" (a brand-new Store loaded from
the database) sees the same rooms, timer state, versions, and idempotency.
"""

import asyncio
import os
import subprocess
import sys
import uuid

import asyncpg
import pytest
from pydantic import TypeAdapter

from app import db
from app.protocol.models import ActorKind, Command, TimerStatus
from app.store import Store

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")
parse = TypeAdapter(Command).validate_python


def migrate() -> None:
    env = {**os.environ, "DATABASE_URL": URL}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env)


async def reset() -> None:
    c = await asyncpg.connect(URL)
    await c.execute("DROP TABLE IF EXISTS commands, rooms, alembic_version CASCADE")
    await c.close()


def command(kind, room, **kw):
    return parse(
        {
            "type": kind, "command_id": str(uuid.uuid4()), "device_id": str(uuid.uuid4()),
            "room_id": room.room_id, "session_id": room.session_id, "claimed_at_ms": 0, **kw,
        }
    )  # fmt: skip


def test_state_survives_restart(monkeypatch):
    monkeypatch.setenv("SEED_ROOMS", "Seed One")
    asyncio.run(reset())
    migrate()

    async def run() -> None:
        pool = await db.connect(URL)
        first = Store()
        await first.load(pool)  # empty DB: seeds
        assert list(first.rooms) == ["seed-one"]
        made = await first.create_room("Persist Hall", 90, "Team Round")
        await first.update_room(made, 100, None)
        permit, start = command("permit", made), None
        await first.apply(made, permit, ActorKind.STAFF)
        start = command("start", made)
        await first.apply(made, start, ActorKind.STAFF)
        stale = parse({**command("pause", made).model_dump(mode="json"), "session_id": "old"})
        await first.apply(made, stale, ActorKind.ROOM)
        want = (made.version, first.snapshot(made).timer.status)
        assert want[1] == TimerStatus.RUNNING

        second = Store()  # "restart"
        await second.load(pool)
        assert sorted(second.rooms) == ["persist-hall", "seed-one"]  # seed not re-run
        back = second.rooms["persist-hall"]
        assert (back.version, second.snapshot(back).timer.status) == want
        assert back.test_name == "Team Round" and back.duration_ms == 100 * 60_000
        again = await second.apply(back, start, ActorKind.STAFF)  # same command_id
        assert again.replayed and back.version == want[0]
        replay_stale = await second.apply(back, stale, ActorKind.ROOM)
        assert replay_stale.replayed
        await pool.close()

    asyncio.run(run())


def test_failed_commit_leaves_memory_untouched(monkeypatch):
    asyncio.run(reset())
    migrate()

    async def run() -> None:
        pool = await db.connect(URL)
        store = Store()
        await store.load(pool)
        room = next(iter(store.rooms.values()))
        before = (room.version, len(room.events))
        await pool.close()  # database "goes away"
        with pytest.raises(Exception):  # noqa: B017 - any driver error
            await store.apply(room, command("permit", room), ActorKind.STAFF)
        assert (room.version, len(room.events)) == before
        assert not room.seen

    asyncio.run(run())
