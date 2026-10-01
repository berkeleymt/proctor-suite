"""Reference implementation of the timer fold (plan §3.3-3.4; docs/protocol.md §5).

Status: written in Phase 0 so the shared fixtures in contracts/timer-fixtures/ can be checked
mechanically. Ian's engine owns this file from Phase 1 on and may restructure it, but it must
keep passing every fixture. The TypeScript twin (web/packages/sync-core) must pass the same ones.

Pure functions only: no I/O, no clocks, no globals.
"""

from dataclasses import dataclass

from app.protocol.constants import MAX_ADJUST_MS
from app.protocol.models import ActorKind, EventType, RejectionReason, TimerSnapshot, TimerStatus


@dataclass(frozen=True)
class SessionSpec:
    session_id: str
    duration_ms: int
    created_at_ms: int


@dataclass(frozen=True)
class TimerEvent:
    command_id: str
    type: EventType
    actor_kind: ActorKind
    received_at_ms: int
    claimed_at_ms: int | None = None
    delta_ms: int | None = None


@dataclass(frozen=True)
class EventResult:
    command_id: str
    applied: bool
    reason: RejectionReason | None


@dataclass(frozen=True)
class FoldResult:
    snapshot: TimerSnapshot
    remaining_ms: int
    results: list[EventResult]  # same order as the (received) input events


class _State:
    def __init__(self, session: SessionSpec) -> None:
        self.duration = session.duration_ms
        self.status = TimerStatus.NOT_PERMITTED
        self.adjust_total = 0
        self.banked = 0
        self.running_since: int | None = None

    def remaining(self, t: int) -> int:
        running = (t - self.running_since) if self.running_since is not None else 0
        return self.duration + self.adjust_total - self.banked - running

    def expire_if_due(self, t: int) -> None:
        """Time reaching zero ends the session (derived; no stored END event is needed)."""
        if self.status in (TimerStatus.RUNNING, TimerStatus.PAUSED) and self.remaining(t) <= 0:
            if self.status is TimerStatus.RUNNING:
                self.banked = self.duration + self.adjust_total  # remaining is exactly 0
                self.running_since = None
            self.status = TimerStatus.ENDED

    def bank(self, t: int) -> None:
        assert self.running_since is not None
        self.banked += t - self.running_since
        self.running_since = None


def _reject(reason: RejectionReason) -> tuple[bool, RejectionReason | None]:
    return False, reason


_OK: tuple[bool, RejectionReason | None] = (True, None)


def _apply(s: _State, e: TimerEvent, t: int) -> tuple[bool, RejectionReason | None]:
    s.expire_if_due(t)
    if s.status is TimerStatus.ENDED:
        return _reject(RejectionReason.SESSION_ENDED)

    match e.type:
        case EventType.PERMIT:
            if s.status is not TimerStatus.NOT_PERMITTED:
                return _reject(RejectionReason.ALREADY_PERMITTED)
            s.status = TimerStatus.PERMITTED
        case EventType.START:
            if s.status is TimerStatus.NOT_PERMITTED:
                return _reject(RejectionReason.NOT_PERMITTED)
            if s.status is not TimerStatus.PERMITTED:
                return _reject(RejectionReason.ALREADY_STARTED)
            s.status = TimerStatus.RUNNING
            s.running_since = t
        case EventType.PAUSE:
            if s.status is not TimerStatus.RUNNING:
                return _reject(RejectionReason.NOT_RUNNING)
            s.bank(t)
            s.status = TimerStatus.PAUSED
        case EventType.RESUME:
            if s.status is not TimerStatus.PAUSED:
                return _reject(RejectionReason.NOT_PAUSED)
            s.status = TimerStatus.RUNNING
            s.running_since = t
        case EventType.END:
            if s.status not in (TimerStatus.RUNNING, TimerStatus.PAUSED):
                return _reject(RejectionReason.NOT_STARTED)
            if s.status is TimerStatus.RUNNING:
                s.bank(t)
            s.status = TimerStatus.ENDED
        case EventType.ADJUST:
            d = e.delta_ms
            if d is None or d == 0 or abs(d) > MAX_ADJUST_MS:
                return _reject(RejectionReason.ADJUST_OUT_OF_RANGE)
            s.adjust_total += d
    return _OK


def fold(session: SessionSpec, events: list[TimerEvent], now_ms: int) -> FoldResult:
    """Fold the events the server has *received by now_ms* into a snapshot as of now_ms.

    Order: room events take effect at claimed_at_ms, staff events at received_at_ms; ties break
    on received_at_ms, then command_id. Invalid transitions are rejected, not dropped.
    SYSTEM events are informational and ignored.
    """
    known = [
        e for e in events if e.received_at_ms <= now_ms and e.actor_kind is not ActorKind.SYSTEM
    ]
    verdict: dict[str, tuple[bool, RejectionReason | None]] = {}
    queue: list[tuple[int, int, str, TimerEvent]] = []

    for e in known:
        if e.actor_kind is ActorKind.ROOM:
            c = e.claimed_at_ms
            if c is None or not (session.created_at_ms <= c <= e.received_at_ms):
                verdict[e.command_id] = _reject(RejectionReason.CLAIMED_AT_OUT_OF_BOUNDS)
                continue
            effective = c
        else:
            effective = e.received_at_ms
        queue.append((effective, e.received_at_ms, e.command_id, e))

    queue.sort(key=lambda q: q[:3])
    state = _State(session)
    for effective, _, _, e in queue:
        verdict[e.command_id] = _apply(state, e, effective)

    state.expire_if_due(now_ms)
    snapshot = TimerSnapshot(
        status=state.status,
        duration_ms=state.duration,
        adjust_total_ms=state.adjust_total,
        elapsed_banked_ms=state.banked,
        running_since_ms=state.running_since,
    )
    results = [EventResult(e.command_id, *verdict[e.command_id]) for e in known]
    return FoldResult(snapshot, max(0, state.remaining(now_ms)), results)
