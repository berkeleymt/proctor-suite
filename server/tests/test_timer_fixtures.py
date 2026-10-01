"""Runs every shared fixture in contracts/timer-fixtures/ against the Python fold.

The TypeScript fold (web/packages/sync-core) must run the same files. See
contracts/timer-fixtures/README.md for the format.
"""

import json
from pathlib import Path

import pytest

from app.fold import SessionSpec, TimerEvent, fold
from app.protocol.models import ActorKind, EventType

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "contracts" / "timer-fixtures"
FILES = sorted(FIXTURE_DIR.glob("*.json"))
FAR_FUTURE = 10**15


def load(path: Path):
    data = json.loads(path.read_text())
    session = SessionSpec(**data["session"])
    events = [
        TimerEvent(
            command_id=e["command_id"],
            type=EventType(e["type"]),
            actor_kind=ActorKind(e["actor_kind"]),
            received_at_ms=e["received_at_ms"],
            claimed_at_ms=e.get("claimed_at_ms"),
            delta_ms=e.get("delta_ms"),
        )
        for e in data["events"]
    ]
    return data, session, events


def test_fixtures_exist():
    assert len(FILES) >= 20


def test_fixture_names_match_filenames_and_are_unique():
    names = [json.loads(p.read_text())["name"] for p in FILES]
    assert len(set(names)) == len(names)
    for p, n in zip(FILES, names, strict=True):
        assert p.stem.split("-", 1)[1] == n


@pytest.mark.parametrize("path", FILES, ids=[p.stem for p in FILES])
def test_event_results(path):
    data, session, events = load(path)
    got = fold(session, events, FAR_FUTURE).results
    want = data["expected"]["event_results"]
    assert [r.command_id for r in got] == [w["command_id"] for w in want]
    for r, w in zip(got, want, strict=True):
        assert ("applied" if r.applied else "rejected") == w["result"], w["command_id"]
        assert (r.reason.value if r.reason else None) == w["reason"], w["command_id"]


@pytest.mark.parametrize("path", FILES, ids=[p.stem for p in FILES])
def test_snapshots_at_probe_times(path):
    data, session, events = load(path)
    for probe in data["expected"]["at"]:
        got = fold(session, events, probe["now_ms"])
        assert got.snapshot.model_dump(mode="json") == probe["snapshot"], probe["now_ms"]
        assert got.remaining_ms == probe["remaining_ms"], probe["now_ms"]
