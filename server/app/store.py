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
from dataclasses import dataclass, field, replace
from uuid import UUID, uuid4

from app import db
from app.fold import SessionSpec, TimerEvent, fold
from app.protocol.constants import MAX_ADMIN_CLARIFICATIONS, MAX_ROOM_CLARIFICATIONS
from app.protocol.models import (
    ActorKind,
    ClarificationAdmin,
    ClarificationOut,
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
    doc_url: str | None = None
    deleted: bool = False  # soft delete: hidden from devices, restorable by an admin
    session_seq: int = 1  # bumped by an admin Reset: a fresh timer, old history kept in Postgres
    session_created_ms: int | None = None
    events: list[TimerEvent] = field(default_factory=list)
    seen: dict[UUID, tuple[tuple, CommandOutcome, RejectionReason | None]] = field(
        default_factory=dict
    )

    @property
    def session_id(self) -> str:
        return f"{self.room_id}-{self.session_seq}"


@dataclass
class Clarification:
    id: UUID
    body: str
    room_ids: list[str] | None  # None = all rooms
    created_at_ms: int
    rev: int  # store-wide counter value when this row last changed
    hidden: bool = False

    def shows_in(self, room_id: str) -> bool:
        return not self.hidden and (self.room_ids is None or room_id in self.room_ids)


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
        self.clars: dict[UUID, Clarification] = {}
        # Added to every room's version so a clarification change reaches all affected rooms
        # without rewriting each room row. Rebuilt at startup as max(rev). Only ever grows.
        self.clar_rev = 0
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
                test_name=r["test_name"], version=r["version"], doc_url=r["doc_url"],
                deleted=r["deleted"], session_seq=r["session_seq"],
                session_created_ms=r["session_created_ms"],
            )  # fmt: skip
        for c in cmds:
            room = loaded.get(c["room_id"])
            if not room:
                continue
            if c["is_event"] and c["session_id"] == room.session_id:
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
        for c in await db.load_clarifications(pool):
            self.clars[c["id"]] = Clarification(
                c["id"], c["body"], c["room_ids"], c["created_at_ms"], c["rev"], c["hidden"]
            )
            self.clar_rev = max(self.clar_rev, c["rev"])

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
    async def _commit(self, room: Room, audit: dict | None = None, **changes) -> None:
        """Apply `changes` to a room: write Postgres first, then memory, bump version, notify."""
        changes["version"] = room.version + 1
        if self.pool:
            await db.save_room(self.pool, replace(room, **changes), audit)
        for k, v in changes.items():
            setattr(room, k, v)
        self.hub.notify(room.room_id)

    async def create_room(
        self, name: str, duration_min: int, test_name: str | None = None, doc_url: str | None = None
    ) -> Room:
        name = " ".join(name.split())
        slug = _slug(name)
        if not slug:
            raise ValueError("invalid_name")
        async with self._admin_lock:
            if slug in self.rooms:
                raise KeyError(slug)
            room = Room(slug, name, duration_min * 60_000, now_ms(), doc_url=doc_url or None)
            if test_name and test_name.strip():
                room.test_name = " ".join(test_name.split())
            if self.pool:
                await db.insert_room(self.pool, room)
            self.rooms[slug] = room
            self.hub.notify(slug)
            return room

    def status(self, room: Room) -> TimerStatus:
        return self.snapshot(room).timer.status

    async def update_room(
        self,
        room: Room,
        duration_min: int | None = None,
        test_name: str | None = None,
        name: str | None = None,
        doc_url: str | None = None,
    ) -> None:
        """Edit a room. Duration only before start. The id never changes on rename (cookies and
        history stay attached); two rooms can't share a name."""
        async with self._admin_lock, self.lock(room.room_id):
            if room.deleted:
                raise LookupError("room_deleted")
            ch: dict = {}
            if duration_min is not None:
                if self.status(room) not in (TimerStatus.NOT_PERMITTED, TimerStatus.PERMITTED):
                    raise PermissionError("room_started")
                ch["duration_ms"] = duration_min * 60_000
            if test_name is not None:
                ch["test_name"] = " ".join(test_name.split())
            if doc_url is not None:
                ch["doc_url"] = doc_url or None
            if name is not None:
                name = " ".join(name.split())
                slug = _slug(name)
                if not slug:
                    raise ValueError("invalid_name")
                if any(
                    o is not room and (o.room_id == slug or o.name.lower() == name.lower())
                    for o in self.rooms.values()
                ):
                    raise KeyError(slug)
                ch["name"] = name
            await self._commit(room, **ch)

    async def delete_room(self, room: Room) -> None:
        """Soft delete. Not while a timer is in progress. Signs the room's devices out."""
        async with self.lock(room.room_id):
            if room.deleted:
                return
            if self.status(room) in (TimerStatus.RUNNING, TimerStatus.PAUSED):
                raise PermissionError("room_in_progress")
            await self._commit(room, deleted=True)
            for tok in [t for t, s in self.sessions.items() if s.room_id == room.room_id]:
                del self.sessions[tok]

    async def restore_room(self, room: Room) -> None:
        async with self.lock(room.room_id):
            if room.deleted:
                await self._commit(room, deleted=False)

    async def reset_room(self, room: Room, session_id: str) -> None:
        """Fresh not-started timer (new session); only from PAUSED or ENDED. History is kept."""
        async with self.lock(room.room_id):
            if room.deleted:
                raise LookupError("room_deleted")
            if session_id != room.session_id:
                raise RuntimeError("stale_session")
            if self.status(room) not in (TimerStatus.PAUSED, TimerStatus.ENDED):
                raise PermissionError("not_resettable")
            t = now_ms()
            audit = {
                "command_id": uuid4(), "room_id": room.room_id, "type": "reset",
                "session_id": room.session_id, "actor_kind": "staff", "claimed_at_ms": None,
                "received_at_ms": t, "delta_ms": None, "is_event": False,
                "outcome": "applied", "reason": None,
            }  # fmt: skip
            await self._commit(
                room, audit, session_seq=room.session_seq + 1, session_created_ms=t, events=[]
            )

    # --- clarifications (commit first, then memory, then tell the affected rooms) ---
    def _notify_targets(self, x: Clarification) -> None:
        for rid in x.room_ids if x.room_ids is not None else list(self.rooms):
            self.hub.notify(rid)

    async def post_clarification(self, body: str, room_ids: list[str] | None) -> Clarification:
        body = body.strip()
        if not body:
            raise ValueError("empty")
        if room_ids is not None:
            room_ids = sorted(set(room_ids))
            if any(r not in self.rooms or self.rooms[r].deleted for r in room_ids):
                raise KeyError("unknown_room")
        async with self._admin_lock:
            x = Clarification(uuid4(), body, room_ids, now_ms(), self.clar_rev + 1)
            if self.pool:
                await db.insert_clarification(self.pool, x)
            self.clars[x.id] = x
            self.clar_rev = x.rev
            self._notify_targets(x)
            return x

    async def hide_clarification(self, cid: UUID, hidden: bool) -> Clarification:
        async with self._admin_lock:
            x = self.clars[cid]  # KeyError -> 404
            if x.hidden != hidden:
                rev = self.clar_rev + 1
                if self.pool:
                    await db.set_clarification_hidden(self.pool, x, hidden, rev)
                x.hidden, x.rev, self.clar_rev = hidden, rev, rev
                self._notify_targets(x)
            return x

    def clarifications_for(self, room: Room) -> list[ClarificationOut]:
        mine = [x for x in self.clars.values() if x.shows_in(room.room_id)]
        mine.sort(key=lambda x: (x.created_at_ms, str(x.id)))
        return [
            ClarificationOut(id=x.id, body=x.body, created_at_ms=x.created_at_ms)
            for x in mine[-MAX_ROOM_CLARIFICATIONS:]
        ]

    def clarifications_admin(self) -> list[ClarificationAdmin]:
        xs = sorted(self.clars.values(), key=lambda x: (x.created_at_ms, str(x.id)), reverse=True)
        return [
            ClarificationAdmin(
                id=x.id, body=x.body, created_at_ms=x.created_at_ms,
                room_ids=x.room_ids, hidden=x.hidden,
            )
            for x in xs[:MAX_ADMIN_CLARIFICATIONS]
        ]  # fmt: skip

    # --- snapshots ---
    def snapshot(self, room: Room, with_clar: bool = True) -> RoomSnapshot:
        t = now_ms()
        spec = SessionSpec(
            room.session_id, room.duration_ms, room.session_created_ms or room.created_at_ms
        )
        timer = fold(spec, room.events, t).snapshot
        return RoomSnapshot(
            room_id=room.room_id,
            room_name=room.name,
            test_name=room.test_name,
            session_id=room.session_id,
            version=self.version(room),
            server_time_ms=t,
            timer=timer,
            deleted=room.deleted,
            doc_url=room.doc_url,
            clarifications=self.clarifications_for(room) if with_clar else [],
        )

    def version(self, room: Room) -> int:
        return room.version + self.clar_rev

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
            spec = SessionSpec(
                room.session_id, room.duration_ms, room.session_created_ms or room.created_at_ms
            )
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
