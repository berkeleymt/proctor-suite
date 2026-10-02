import asyncio
import json
import uuid

from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from app.main import app
from app.protocol.models import ActorKind, Command
from app.store import Store
from app.stream import frames

H = {"X-Proctor-Client": "t"}
parse = TypeAdapter(Command).validate_python


def decode(frame: str) -> tuple[str, dict]:
    lines = dict(line.split(": ", 1) for line in frame.strip().split("\n"))
    return lines["event"], json.loads(lines["data"])


def test_room_stream_sends_initial_changes_and_heartbeat(monkeypatch):
    monkeypatch.setenv("SEED_ROOMS", "One,Two")

    async def run() -> None:
        store = Store()
        one, two = store.rooms["one"], store.rooms["two"]
        gen = frames(store, "one", heartbeat_s=0.05)
        ev, snap = decode(await anext(gen))
        assert ev == "snapshot" and snap["room_id"] == "one"
        assert decode(await anext(gen))[0] == "heartbeat"  # quiet room
        cmd = parse(
            {
                "type": "permit", "command_id": str(uuid.uuid4()), "device_id": str(uuid.uuid4()),
                "room_id": "one", "session_id": one.session_id, "claimed_at_ms": 0,
            }
        )  # fmt: skip
        await store.apply(
            two,
            cmd.model_copy(update={"room_id": "two", "session_id": two.session_id}),
            ActorKind.STAFF,
        )
        await store.apply(one, cmd, ActorKind.STAFF)
        ev, snap = decode(await anext(gen))  # only room one's change arrives, not room two's
        assert (
            ev == "snapshot" and snap["room_id"] == "one" and snap["timer"]["status"] == "PERMITTED"
        )
        await gen.aclose()
        assert store.hub.count == 0  # unsubscribed

    asyncio.run(run())


def test_staff_stream_gets_every_room_and_new_rooms(monkeypatch):
    monkeypatch.setenv("SEED_ROOMS", "One,Two")

    async def run() -> None:
        store = Store()
        gen = frames(store, None, heartbeat_s=5)
        first = [decode(await anext(gen))[1]["room_id"] for _ in range(2)]
        assert first == ["one", "two"]
        await store.create_room("Three", 60)
        assert decode(await anext(gen))[1]["room_id"] == "three"
        await gen.aclose()

    asyncio.run(run())


def test_stream_endpoints_need_the_right_login(monkeypatch):
    monkeypatch.setenv("ROOM_PASSWORD", "room-pw")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-pw")
    c = TestClient(app, base_url="https://testserver")
    assert c.get("/api/staff/stream").status_code == 401
    assert c.get("/api/rooms/nope/stream").status_code == 404
    room = c.get("/api/auth/rooms").json()["rooms"][0]["room_id"]
    assert c.get(f"/api/rooms/{room}/stream").status_code == 401


def test_staff_stream_clarifications_event_and_room_removed(monkeypatch):
    monkeypatch.setenv("SEED_ROOMS", "One,Two")

    async def run() -> None:
        store = Store()
        gen = frames(store, None, heartbeat_s=5, clars=True)
        first = [decode(await anext(gen)) for _ in range(3)]  # 2 room snapshots, then the list
        assert [e for e, _ in first] == ["snapshot", "snapshot", "clarifications"]
        assert first[2][1]["clarifications"] == []
        await store.post_clarification("Hello", None)
        got: dict[str, list] = {}
        for _ in range(3):  # both rooms hear about it, and so does the admin list
            ev, data = decode(await anext(gen))
            got.setdefault(ev, []).append(data)
        assert [x["body"] for x in got["clarifications"][-1]["clarifications"]] == ["Hello"]
        # a delete is soft: the list still carries it, flagged
        x = next(iter(store.clars.values()))
        await store.delete_clarification(x.id)
        seen = [decode(await anext(gen)) for _ in range(3)]
        listing = next(d for e, d in seen if e == "clarifications")
        assert listing["clarifications"][0]["deleted"] is True
        # emptying a deleted room tells staff to drop it
        two = store.rooms["two"]
        await store.delete_room(two)
        assert decode(await anext(gen))[0] == "snapshot"
        await store.empty_room(two)
        assert decode(await anext(gen)) == ("room_removed", {"room_id": "two"})
        await gen.aclose()

    asyncio.run(run())


def test_staff_stream_without_flag_sends_no_clarifications(monkeypatch):
    monkeypatch.setenv("SEED_ROOMS", "One")

    async def run() -> None:
        store = Store()
        gen = frames(store, None, heartbeat_s=0.05)
        names = [decode(await anext(gen))[0]]
        await store.post_clarification("Hello", None)
        names += [decode(await anext(gen))[0] for _ in range(2)]
        assert "clarifications" not in names
        await gen.aclose()

    asyncio.run(run())
