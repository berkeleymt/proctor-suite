"""Slice 1 in-memory store: rooms, sessions, commands.

KNOWN GAP (docs/status/log/2026-10-01-claude-slice1.md): nothing is persisted yet.
Invariant 5 (commit to Postgres before memory) is NOT met until slice 2.
Do not use for a real event.
"""

import hmac
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from uuid import UUID

from app.fold import SessionSpec, TimerEvent, fold
from app.protocol.models import (
    ActorKind,
    CommandOutcome,
    CommandResponse,
    EventType,
    RejectionReason,
    RoomSnapshot,
    StaffRole,
)

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

    # --- auth ---
    @staticmethod
    def check_password(given: str, env_name: str) -> bool:
        want = os.environ.get(env_name, "")
        return bool(want) and hmac.compare_digest(given.encode(), want.encode())

    def new_session(self, s: Session) -> str:
        token = secrets.token_urlsafe(32)
        self.sessions[token] = s
        return token

    # --- rooms ---
    def create_room(self, name: str, duration_min: int) -> Room:
        name = " ".join(name.split())
        slug = _slug(name)
        if not slug:
            raise ValueError("invalid_name")
        if slug in self.rooms:
            raise KeyError(slug)
        room = Room(slug, name, duration_min * 60_000, now_ms())
        self.rooms[slug] = room
        return room

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
    def apply(self, room: Room, cmd, actor: ActorKind) -> CommandResponse:
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
            room.events.append(ev)
            spec = SessionSpec(room.session_id, room.duration_ms, room.created_at_ms)
            res = next(
                r
                for r in fold(spec, room.events, now_ms()).results
                if r.command_id == ev.command_id
            )
            outcome = CommandOutcome.APPLIED if res.applied else CommandOutcome.REJECTED
            reason = res.reason
            room.version += 1
        room.seen[cmd.command_id] = (key, outcome, reason)
        return CommandResponse(
            command_id=cmd.command_id,
            outcome=outcome,
            reason=reason,
            replayed=False,
            snapshot=self.snapshot(room),
        )
