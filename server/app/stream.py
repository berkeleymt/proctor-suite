"""Server-Sent Events (protocol §7.2). Every frame is a whole RoomSnapshot, so a dropped or
duplicated frame can never leave a client half-updated, and no Last-Event-ID resume is needed.

Memory-bounded (invariant 8): each subscriber holds a set of room ids (at most the number of
rooms), not a queue of frames. A slow client simply gets the latest snapshot of each dirty room.
"""

import asyncio
import json
from collections.abc import AsyncIterator

from app.protocol.constants import HEARTBEAT_INTERVAL_S


class Sub:
    def __init__(self, room_id: str | None) -> None:
        self.room_id = room_id  # None = staff: every room
        self.dirty: set[str] = set()
        self.wake = asyncio.Event()


class Hub:
    def __init__(self) -> None:
        self._subs: set[Sub] = set()

    @property
    def count(self) -> int:
        return len(self._subs)

    def subscribe(self, room_id: str | None) -> Sub:
        sub = Sub(room_id)
        self._subs.add(sub)
        return sub

    def unsubscribe(self, sub: Sub) -> None:
        self._subs.discard(sub)

    def notify(self, room_id: str) -> None:
        """Called after a change is committed and applied in memory (invariant 5)."""
        for sub in self._subs:
            if sub.room_id in (None, room_id):
                sub.dirty.add(room_id)
                sub.wake.set()


def _frame(event: str, data: str, version: int | None = None) -> str:
    head = f"event: {event}\n" + (f"id: {version}\n" if version is not None else "")
    return f"{head}data: {data}\n\n"


async def frames(
    store, room_id: str | None, heartbeat_s: float = HEARTBEAT_INTERVAL_S
) -> AsyncIterator[str]:
    """Initial snapshot(s), then one snapshot per change, a heartbeat after each quiet interval."""
    from app.store import now_ms  # local import: store imports this module

    sub = store.hub.subscribe(
        room_id
    )  # subscribe first so nothing between snapshot and loop is lost
    try:
        for rid in [room_id] if room_id else sorted(store.rooms):
            room = store.rooms.get(rid)
            if room:
                snap = store.snapshot(room)
                yield _frame("snapshot", snap.model_dump_json(), snap.version)
        while True:
            try:
                await asyncio.wait_for(sub.wake.wait(), heartbeat_s)
            except TimeoutError:
                yield _frame("heartbeat", json.dumps({"server_time_ms": now_ms()}))
                continue
            sub.wake.clear()
            dirty, sub.dirty = sorted(sub.dirty), set()
            for rid in dirty:
                room = store.rooms.get(rid)
                if room:
                    snap = store.snapshot(room)
                    yield _frame("snapshot", snap.model_dump_json(), snap.version)
    finally:
        store.hub.unsubscribe(sub)
