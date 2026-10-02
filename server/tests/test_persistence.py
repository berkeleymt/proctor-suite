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
    await c.execute(
        "DROP TABLE IF EXISTS bathroom_visits, super_admins, settings, clar_counter, clarifications, commands, rooms, alembic_version CASCADE"
    )
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


def test_reset_delete_rename_survive_restart(monkeypatch):
    monkeypatch.setenv("SEED_ROOMS", "Seed One")
    asyncio.run(reset())
    migrate()  # runs 0001 then 0002

    async def run() -> None:
        pool = await db.connect(URL)
        first = Store()
        await first.load(pool)
        room = await first.create_room("Keep Hall", 60, doc_url="https://example.com/d")
        await first.apply(room, command("permit", room), ActorKind.STAFF)
        await first.apply(room, command("start", room), ActorKind.STAFF)
        await first.apply(room, command("pause", room), ActorKind.STAFF)
        old_session = room.session_id
        await first.reset_room(room, old_session)
        await first.update_room(room, name="Kept Hall", doc_url="")
        gone = await first.create_room("Gone Hall", 60)
        await first.delete_room(gone)
        want = (room.session_id, room.version, first.snapshot(room).timer.status)
        assert want[0] != old_session and want[2] == TimerStatus.NOT_PERMITTED

        second = Store()  # "restart"
        await second.load(pool)
        back = second.rooms["keep-hall"]
        assert (back.session_id, back.version, second.snapshot(back).timer.status) == want
        assert back.name == "Kept Hall" and back.doc_url is None and not back.events
        assert second.rooms["gone-hall"].deleted
        await pool.close()

    asyncio.run(run())


def test_clarifications_survive_restart(monkeypatch):
    monkeypatch.setenv("SEED_ROOMS", "Clar One,Clar Two")
    asyncio.run(reset())
    migrate()

    async def run() -> None:
        pool = await db.connect(URL)
        first = Store()
        await first.load(pool)
        x = await first.post_clarification("All see this", None)
        y = await first.post_clarification("Only one", ["clar-one"])
        await first.hide_clarification(x.id, True)
        want = first.version(first.rooms["clar-two"])
        second = Store()
        await second.load(pool)
        two, one = second.rooms["clar-two"], second.rooms["clar-one"]
        assert [c.body for c in second.clarifications_for(one)] == ["Only one"]
        assert second.clarifications_for(two) == []
        assert second.version(two) == want  # versions never go backwards across a restart
        assert y.id in second.clars
        await pool.close()

    asyncio.run(run())


def test_clarification_edit_per_room_and_delete_survive_restart(monkeypatch):
    monkeypatch.setenv("SEED_ROOMS", "Clar One,Clar Two")
    asyncio.run(reset())
    migrate()

    async def run() -> None:
        pool = await db.connect(URL)
        first = Store()
        await first.load(pool)
        x = await first.post_clarification("Original", None)
        gone = await first.post_clarification("Wipe me", None)
        await first.edit_clarification(x.id, "Corrected")
        await first.hide_clarification(x.id, True, "clar-one")
        await first.delete_clarification(x.id, "clar-two")
        await first.delete_clarification(gone.id)  # soft: still in the database
        soft = await first.post_clarification("Soft", None)
        await first.delete_clarification(soft.id)
        mine = await first.post_clarification("For both", None)
        copy = await first.edit_clarification(mine.id, "For both, fixed", "clar-one")
        await first.empty_clarification(gone.id)  # highest rev lives only in clar_counter now
        want = first.version(first.rooms["clar-one"])

        second = Store()
        await second.load(pool)
        back = second.clars[x.id]
        assert (back.body, back.previous) == ("Corrected", ["Original"])
        assert back.edited_at_ms is not None
        assert (back.hidden_room_ids, back.removed_room_ids) == (["clar-one"], ["clar-two"])
        assert gone.id not in second.clars
        assert second.clars[soft.id].deleted
        assert second.clars[mine.id].edited_room_ids == ["clar-one"]
        assert second.clars[copy.id].room_ids == ["clar-one"]
        assert second.clars[copy.id].previous == ["For both"]
        assert second.version(second.rooms["clar-one"]) == want  # no step backwards after delete
        await pool.close()

    asyncio.run(run())


def test_settings_and_super_admins_survive_restart(monkeypatch):
    monkeypatch.setenv("ROOM_PASSWORD", "from-env")
    asyncio.run(reset())
    migrate()

    async def run() -> None:
        pool = await db.connect(URL)
        first = Store()
        await first.load(pool)
        await first.update_settings(
            {"APP_NAME": "Lemma", "ROOM_PASSWORD": "from-db"}, "a@b.co", set()
        )
        await first.add_super("helper@berkeley.mt", "a@b.co")
        await first.add_super("gone@berkeley.mt", "a@b.co")
        await first.remove_super("gone@berkeley.mt")
        second = Store()  # "restart"
        await second.load(pool)
        assert second.brand()[0] == "Lemma"
        assert second.check_password("from-db", "ROOM_PASSWORD")  # the database beats .env
        assert not second.check_password("from-env", "ROOM_PASSWORD")
        assert list(second.supers) == ["helper@berkeley.mt"]
        await pool.close()

    asyncio.run(run())


def test_bathroom_log_survives_restart_and_goes_with_its_room(monkeypatch):
    monkeypatch.setenv("SEED_ROOMS", "Bath Seed")
    asyncio.run(reset())
    migrate()

    async def run() -> None:
        pool = await db.connect(URL)
        first = Store()
        await first.load(pool)
        room = first.rooms["bath-seed"]
        a, b = uuid.uuid4(), uuid.uuid4()
        await first.bathroom_out(room, a, "054A")
        await first.bathroom_out(room, b, "117C")
        await first.bathroom_return(room, a)
        second = Store()
        await second.load(pool)  # a restart
        snap = second.snapshot(second.rooms["bath-seed"])
        assert [v.student_id for v in snap.bathroom_out] == ["117C"] and snap.students_out == 1
        assert [v.student_id for v in snap.bathroom_back] == ["054A"]
        assert snap.bathroom_back[0].back_ms is not None
        await second.delete_room(second.rooms["bath-seed"])
        await second.empty_room(second.rooms["bath-seed"])  # rows leave with the room
        assert await db.load_visits(pool) == []
        await pool.close()

    asyncio.run(run())
