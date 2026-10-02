"""In-memory state (the only thing room devices read) plus write-through to Postgres.

With DATABASE_URL set (lifespan calls `load`), every write commits to Postgres first and only
then changes memory (invariant 5), and state is rebuilt from Postgres at startup. Without it
(unit tests, quick local dev) the Store is memory-only. Sessions (logins) are always memory-only:
a restart logs everyone out.
"""

import asyncio
import hmac
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from uuid import UUID

from app import db
from app.fold import SessionSpec, TimerEvent, fold
from app.protocol.models import (
    ActorKind,
    CommandOutcome,
    CommandResponse,
    EventType,
    RejectionReason,
    RoomSnapshot,
    StaffRole,
    TimerStatus,
)
from app.stream import Hub

DEFAULT_ROOMS = "Dwinelle 145,Evans 10,Soda 306,Wheeler 150"


def now_ms() -> int:
    return int(time.time() * 1000)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@dataclass
class Room:
    room_id: str
    name: str
    duration_ms: int
    created_at_ms: int
    test_name: str = "Individual Round"
    version: int = 1
    events: list[TimerEvent] = field(default_factory=list)
    seen: dict[UUID, tuple[tuple, CommandOutcome, RejectionReason | None]] = field(
        default_factory=dict
    )

    @property
    def session_id(self) -> str:
        return f"{self.room_id}-1"


@dataclass(frozen=True)
class Session:
    kind: str  # "room" | "staff"
    surface: str
    room_id: str | None = None
    role: StaffRole | None = None


class Store:
    def __init__(self) -> None:
        names = [n.strip() for n in os.environ.get("SEED_ROOMS", DEFAULT_ROOMS).split(",")]
        minutes = int(os.environ.get("SESSION_DURATION_MIN", "60"))
        t = now_ms()
        self.event_id = "evt-demo"
        self.event_name = os.environ.get("EVENT_NAME", "BMT (slice 1 demo)")
        self.rooms = {_slug(n): Room(_slug(n), n, minutes * 60_000, t) for n in names if n}
        self.sessions: dict[str, Session] = {}
        self.pool = None  # asyncpg pool when persistence is on
        self.hub = Hub()  # SSE subscribers; notified after every committed change
        self._locks: dict[str, asyncio.Lock] = {}
        self._admin_lock = asyncio.Lock()

    def lock(self, room_id: str) -> asyncio.Lock:
        return self._locks.setdefault(room_id, asyncio.Lock())

    # --- startup: rebuild memory from Postgres (seed on first run) ---
    async def load(self, pool) -> None:
        self.pool = pool
        rooms, cmds = await db.load_rooms(pool)
        if not rooms:
            for r in self.rooms.values():
                await db.insert_room(pool, r)
            return
        loaded: dict[str, Room] = {}
        for r in rooms:
            loaded[r["room_id"]] = Room(
                r["room_id"], r["name"], r["duration_ms"], r["created_at_ms"],
                test_name=r["test_name"], version=r["version"],
            )  # fmt: skip
        for c in cmds:
            room = loaded.get(c["room_id"])
            if not room:
                continue
            if c["is_event"]:
                room.events.append(
                    TimerEvent(
                        command_id=str(c["command_id"]),
                        type=EventType(c["type"].upper()),
                        actor_kind=ActorKind(c["actor_kind"]),
                        received_at_ms=c["received_at_ms"],
                        claimed_at_ms=c["claimed_at_ms"],
                        delta_ms=c["delta_ms"],
                    )
                )
            room.seen[c["command_id"]] = (
                (c["type"], c["session_id"], c["delta_ms"]),
                CommandOutcome(c["outcome"]),
                RejectionReason(c["reason"]) if c["reason"] else None,
            )
        self.rooms = loaded

    # --- auth ---
    @staticmethod
    def check_password(given: str, env_name: str) -> bool:
        want = os.environ.get(env_name, "")
        return bool(want) and hmac.compare_digest(given.encode(), want.encode())

    def new_session(self, s: Session) -> str:
        token = secrets.token_urlsafe(32)
        self.sessions[token] = s
        return token

    # --- rooms (commit first, then memory: invariant 5) ---
    async def create_room(self, name: str, duration_min: int, test_name: str | None = None) -> Room:
        name = " ".join(name.split())
        slug = _slug(name)
        if not slug:
            raise ValueError("invalid_name")
        async with self._admin_lock:
            if slug in self.rooms:
                raise KeyError(slug)
            room = Room(slug, name, duration_min * 60_000, now_ms())
            if test_name and test_name.strip():
                room.test_name = " ".join(test_name.split())
            if self.pool:
                await db.insert_room(self.pool, room)
            self.rooms[slug] = room
            self.hub.notify(slug)
            return room

    async def update_room(
        self, room: Room, duration_min: int | None, test_name: str | None
    ) -> None:
        """Edit duration (only before start) and/or test label. Bumps version so pollers refetch."""
        async with self.lock(room.room_id):
            duration_ms = room.duration_ms
            if duration_min is not None:
                status = self.snapshot(room).timer.status
                if status not in (TimerStatus.NOT_PERMITTED, TimerStatus.PERMITTED):
                    raise PermissionError("room_started")
                duration_ms = duration_min * 60_000
            label = " ".join(test_name.split()) if test_name is not None else room.test_name
            if self.pool:
                await db.save_room_settings(
                    self.pool, room.room_id, label, duration_ms, room.version + 1
                )
            room.duration_ms, room.test_name = duration_ms, label
            room.version += 1
            self.hub.notify(room.room_id)

    # --- snapshots ---
    def snapshot(self, room: Room) -> RoomSnapshot:
        t = now_ms()
        spec = SessionSpec(room.session_id, room.duration_ms, room.created_at_ms)
        timer = fold(spec, room.events, t).snapshot
        return RoomSnapshot(
            room_id=room.room_id,
            room_name=room.name,
            test_name=room.test_name,
            session_id=room.session_id,
            version=room.version,
            server_time_ms=t,
            timer=timer,
        )

    # --- commands (idempotent on command_id; protocol §6.4) ---
    async def apply(self, room: Room, cmd, actor: ActorKind) -> CommandResponse:
        async with self.lock(room.room_id):
            return await self._apply(room, cmd, actor)

    async def _apply(self, room: Room, cmd, actor: ActorKind) -> CommandResponse:
        key = (cmd.type, cmd.session_id, getattr(cmd, "delta_ms", None))
        prior = room.seen.get(cmd.command_id)
        if prior:
            if prior[0] != key:
                raise ValueError("command_id_conflict")
            return CommandResponse(
                command_id=cmd.command_id,
                outcome=prior[1],
                reason=prior[2],
                replayed=True,
                snapshot=self.snapshot(room),
            )
        ev = None
        if cmd.session_id != room.session_id:
            outcome, reason = CommandOutcome.REJECTED, RejectionReason.STALE_SESSION
        else:
            ev = TimerEvent(
                command_id=str(cmd.command_id),
                type=EventType(cmd.type.upper()),
                actor_kind=actor,
                received_at_ms=now_ms(),
                claimed_at_ms=cmd.claimed_at_ms,
                delta_ms=getattr(cmd, "delta_ms", None),
            )
            spec = SessionSpec(room.session_id, room.duration_ms, room.created_at_ms)
            res = next(
                r
                for r in fold(spec, [*room.events, ev], now_ms()).results
                if r.command_id == ev.command_id
            )
            outcome = CommandOutcome.APPLIED if res.applied else CommandOutcome.REJECTED
            reason = res.reason
        version = room.version + (1 if ev else 0)
        if self.pool:  # commit BEFORE memory (invariant 5)
            await db.save_command(
                self.pool,
                {
                    "command_id": cmd.command_id, "room_id": room.room_id, "type": cmd.type,
                    "session_id": cmd.session_id, "actor_kind": actor.value if ev else None,
                    "claimed_at_ms": cmd.claimed_at_ms, "received_at_ms": ev.received_at_ms if ev else None,
                    "delta_ms": getattr(cmd, "delta_ms", None), "is_event": ev is not None,
                    "outcome": outcome.value, "reason": reason.value if reason else None,
                },
                version,
            )  # fmt: skip
        if ev:
            room.events.append(ev)
        room.version = version
        room.seen[cmd.command_id] = (key, outcome, reason)
        if ev:
            self.hub.notify(room.room_id)
        return CommandResponse(
            command_id=cmd.command_id,
            outcome=outcome,
            reason=reason,
            replayed=False,
            snapshot=self.snapshot(room),
        )
