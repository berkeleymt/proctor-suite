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
