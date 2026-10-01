"""Fold rules that the shared fixtures don't pin down (tie-breaking, system events)."""

from app.fold import SessionSpec, TimerEvent, fold
from app.protocol.models import ActorKind, EventType, RejectionReason, TimerStatus

S = SessionSpec("s", duration_ms=600_000, created_at_ms=0)


def staff(cid, typ, rec, **kw):
    return TimerEvent(cid, typ, ActorKind.STAFF, rec, **kw)


def room(cid, typ, claimed, rec):
    return TimerEvent(cid, typ, ActorKind.ROOM, rec, claimed_at_ms=claimed)


def test_tie_on_effective_time_breaks_on_received_then_command_id():
    permit = staff("p", EventType.PERMIT, 1000)
    # Same effective time (5000). b was received earlier, so it wins regardless of id order.
    a = room("a", EventType.START, 5000, 7000)
    b = room("b", EventType.START, 5000, 6000)
    res = {r.command_id: r for r in fold(S, [permit, a, b], 10_000).results}
    assert res["b"].applied and not res["a"].applied
    assert res["a"].reason is RejectionReason.ALREADY_STARTED

    # Same effective AND received time: lower command_id wins.
    c = room("c", EventType.START, 5000, 6000)
    res = {r.command_id: r for r in fold(S, [permit, c, b], 10_000).results}
    assert res["b"].applied and not res["c"].applied


def test_system_events_are_ignored():
    sys_end = TimerEvent("x", EventType.END, ActorKind.SYSTEM, 2000)
    out = fold(S, [staff("p", EventType.PERMIT, 1000), sys_end], 5000)
    assert out.snapshot.status is TimerStatus.PERMITTED
    assert [r.command_id for r in out.results] == ["p"]


def test_events_not_yet_received_are_invisible():
    out = fold(S, [staff("p", EventType.PERMIT, 1000)], 999)
    assert out.snapshot.status is TimerStatus.NOT_PERMITTED
    assert out.results == []


def test_room_event_without_claimed_at_is_rejected():
    ev = TimerEvent("r", EventType.PAUSE, ActorKind.ROOM, 2000, claimed_at_ms=None)
    out = fold(S, [ev], 5000)
    assert out.results[0].reason is RejectionReason.CLAIMED_AT_OUT_OF_BOUNDS


def test_end_before_start_is_rejected():
    out = fold(S, [staff("p", EventType.PERMIT, 1000), staff("e", EventType.END, 2000)], 5000)
    assert out.results[1].reason is RejectionReason.NOT_STARTED
    assert out.snapshot.status is TimerStatus.PERMITTED
