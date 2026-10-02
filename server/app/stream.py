"""Server-Sent Events (protocol §7.2) and room presence.

Every snapshot frame is a whole RoomSnapshot, so a dropped or duplicated frame can never leave a
client half-updated, and no Last-Event-ID resume is needed. Memory-bounded (invariant 8): each
subscriber holds sets of room ids, not queues of frames; a slow client just gets the latest state.

Presence = how many device streams are open per room and surface (control / display) right now,
and when one was last open. In memory only (a restart forgets it until devices reconnect).
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator

from app.protocol.constants import HEARTBEAT_INTERVAL_S

SURFACES = ("control", "display")


def _now() -> int:
    return int(time.time() * 1000)


class Sub:
    def __init__(self, room_id: str | None, surface: str | None, cid: str | None = None) -> None:
        self.room_id = room_id  # None = staff: every room
        self.surface = surface  # counted in presence when set
        self.cid = cid  # the page's own stream id, so it can say "I'm leaving"
        self.closed = False
        self.dirty: set[str] = set()
        self.dirty_presence: set[str] = set()
        self.wake = asyncio.Event()
        self.clars = False  # staff admin list: also wants `clarifications` events
        self.dirty_clar = False
        self.removed: set[str] = set()  # staff: rooms emptied for good (0.8.0)


class Hub:
    def __init__(self) -> None:
        self._subs: set[Sub] = set()
        self._presence: dict[str, dict[str, list]] = {}  # room_id -> surface -> [online, last_seen]

    @property
    def count(self) -> int:
        return len(self._subs)

    def presence(self, room_id: str) -> dict:
        p = self._presence.get(room_id, {})
        return {
            "room_id": room_id,
            **{
                s: {"online": p.get(s, [0, None])[0], "last_seen_ms": p.get(s, [0, None])[1]}
                for s in SURFACES
            },
        }

    def presence_all(self) -> list[dict]:
        return [self.presence(r) for r in sorted(self._presence)]

    def _touch(self, room_id: str, surface: str, delta: int) -> None:
        slot = self._presence.setdefault(room_id, {}).setdefault(surface, [0, None])
        slot[0] = max(0, slot[0] + delta)
        slot[1] = _now()
        for sub in self._subs:
            if sub.room_id is None:
                sub.dirty_presence.add(room_id)
                sub.wake.set()

    def close(self, room_id: str, cid: str) -> None:
        """A page says it is closing: end that stream now instead of at the next failed write."""
        for sub in self._subs:
            if sub.cid == cid and sub.room_id == room_id:
                sub.closed = True
                sub.wake.set()

    def subscribe(
        self,
        room_id: str | None,
        surface: str | None = None,
        cid: str | None = None,
        clars: bool = False,
    ) -> Sub:
        sub = Sub(room_id, surface, cid)
        sub.clars = clars and room_id is None
        self._subs.add(sub)
        if room_id and surface:
            self._touch(room_id, surface, +1)
        return sub

    def unsubscribe(self, sub: Sub) -> None:
        if sub in self._subs:
            self._subs.discard(sub)
            if sub.room_id and sub.surface:
                self._touch(sub.room_id, sub.surface, -1)

    def notify_removed(self, room_id: str) -> None:
        """A room was emptied for good: staff pages drop it without a reload (0.8.0)."""
        for sub in self._subs:
            if sub.room_id is None:
                sub.removed.add(room_id)
                sub.wake.set()

    def notify_clar(self) -> None:
        """The clarification list changed: tell admin pages that asked (0.8.0)."""
        for sub in self._subs:
            if sub.clars:
                sub.dirty_clar = True
                sub.wake.set()

    def notify(self, room_id: str) -> None:
        """Called after a change is committed and applied in memory (invariant 5)."""
        for sub in self._subs:
            if sub.room_id in (None, room_id):
                sub.dirty.add(room_id)
                sub.wake.set()


def _frame(event: str, data: str, version: int | None = None) -> str:
    head = f"event: {event}\n" + (f"id: {version}\n" if version is not None else "")
    return f"{head}data: {data}\n\n"


def _clar_frame(store) -> str:
    from app.protocol.models import ClarificationsResponse

    body = ClarificationsResponse(clarifications=store.clarifications_admin())
    return _frame("clarifications", body.model_dump_json())


async def frames(
    store,
    room_id: str | None,
    heartbeat_s: float = HEARTBEAT_INTERVAL_S,
    surface: str | None = None,
    cid: str | None = None,
    clars: bool = False,
) -> AsyncIterator[str]:
    """Initial snapshot(s), then one per change; a heartbeat after each quiet interval.
    A room stream ends when its room is deleted (the device then re-authenticates and is refused).
    """
    hub: Hub = store.hub
    sub = hub.subscribe(room_id, surface, cid, clars)  # subscribe first so nothing is lost
    try:
        for rid in [room_id] if room_id else sorted(store.rooms):
            room = store.rooms.get(rid)
            if room and not (room_id and room.deleted):
                snap = store.snapshot(room, with_clar=room_id is not None)
                yield _frame("snapshot", snap.model_dump_json(), snap.version)
        if room_id is None:
            for p in hub.presence_all():
                yield _frame("presence", json.dumps(p))
        if sub.clars:
            sub.dirty_clar = False
            yield _clar_frame(store)
        while True:
            try:
                await asyncio.wait_for(sub.wake.wait(), heartbeat_s)
            except TimeoutError:
                yield _frame("heartbeat", json.dumps({"server_time_ms": _now()}))
                continue
            sub.wake.clear()
            if sub.closed:
                return
            dirty, sub.dirty = sorted(sub.dirty), set()
            pres, sub.dirty_presence = sorted(sub.dirty_presence), set()
            if sub.dirty_clar:
                sub.dirty_clar = False
                yield _clar_frame(store)
            for rid in dirty:
                room = store.rooms.get(rid)
                if not room:
                    continue
                if room_id and room.deleted:
                    return
                snap = store.snapshot(room, with_clar=room_id is not None)
                yield _frame("snapshot", snap.model_dump_json(), snap.version)
            for rid in pres:
                yield _frame("presence", json.dumps(hub.presence(rid)))
            gone, sub.removed = sorted(sub.removed), set()
            for rid in gone:
                yield _frame("room_removed", json.dumps({"room_id": rid}))
    finally:
        hub.unsubscribe(sub)
