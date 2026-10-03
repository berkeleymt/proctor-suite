"""Contract tests: wire models parse as documented and contracts/openapi.json is current."""

import json
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.protocol.models import (
    Command,
    CommandResponse,
    HeartbeatMessage,
    RoomSnapshot,
    SetDisplayRequest,
    SnapshotMessage,
)
from scripts.export_openapi import OUT, render

COMMAND = TypeAdapter(Command)


def base(**kw):
    return {
        "command_id": str(uuid4()),
        "device_id": str(uuid4()),
        "room_id": "room-1",
        "session_id": "sess-1",
        "claimed_at_ms": 1000,
        **kw,
    }


@pytest.mark.parametrize("t", ["permit", "start", "pause", "resume", "end"])
def test_simple_commands_parse(t):
    assert COMMAND.validate_python(base(type=t)).type == t


def test_adjust_requires_delta_but_not_range():
    assert COMMAND.validate_python(base(type="adjust", delta_ms=10**12)).delta_ms == 10**12
    with pytest.raises(ValidationError):
        COMMAND.validate_python(base(type="adjust"))


def test_unknown_command_type_and_extra_fields_fail():
    with pytest.raises(ValidationError):
        COMMAND.validate_python(base(type="explode"))
    with pytest.raises(ValidationError):
        COMMAND.validate_python(base(type="pause", surprise=1))


def test_command_id_must_be_uuid():
    with pytest.raises(ValidationError):
        COMMAND.validate_python(base(type="pause", command_id="not-a-uuid"))


SNAPSHOT = {
    "room_id": "room-1",
    "room_name": "Evans 60",
    "test_name": "Individual Round",
    "session_id": "sess-1",
    "version": 3,
    "server_time_ms": 123,
    "deleted": False,
    "doc_url": None,
    "clarifications": [],
    "students_out": 0,
    "bathroom_out": [],
    "bathroom_back": [],
    "display": {
        "timer_zoom_pct": 80,
        "clar_size": "auto",
        "timer_zoom_at_ms": None,
        "clar_size_at_ms": 4000,
    },
    "timer": {
        "status": "RUNNING",
        "duration_ms": 600000,
        "adjust_total_ms": 0,
        "elapsed_banked_ms": 0,
        "running_since_ms": 5000,
    },
}


def test_snapshot_round_trip_and_all_fields_required():
    assert RoomSnapshot.model_validate(SNAPSHOT).model_dump(mode="json") == SNAPSHOT
    broken = json.loads(json.dumps(SNAPSHOT))
    del broken["timer"]["running_since_ms"]  # nullable, but must be present
    with pytest.raises(ValidationError):
        RoomSnapshot.model_validate(broken)
    no_at = json.loads(json.dumps(SNAPSHOT))
    del no_at["display"]["timer_zoom_at_ms"]
    with pytest.raises(ValidationError):
        RoomSnapshot.model_validate(no_at)


def display_req(**kw):
    return {"command_id": str(uuid4()), "claimed_at_ms": 1000, **kw}


@pytest.mark.parametrize(
    "kw", [{"timer_zoom_pct": 40}, {"timer_zoom_pct": 100}, {"clar_size": 0}, {"clar_size": 7},
           {"clar_size": "auto"}, {"timer_zoom_pct": 90, "clar_size": 3}, {}],
)  # fmt: skip
def test_set_display_accepts_the_steps(kw):
    assert SetDisplayRequest.model_validate(display_req(**kw))


@pytest.mark.parametrize(
    "kw", [{"timer_zoom_pct": 85}, {"timer_zoom_pct": 0}, {"timer_zoom_pct": "80"},
           {"clar_size": 8}, {"clar_size": -1}, {"clar_size": "big"}, {"clar_size": True},
           {"clar_size": 2.5}, {"surprise": 1}],
)  # fmt: skip
def test_set_display_rejects_anything_else(kw):
    with pytest.raises(ValidationError):
        SetDisplayRequest.model_validate(display_req(**kw))


def test_command_response_and_sse_messages():
    cid = str(uuid4())
    r = CommandResponse.model_validate(
        {
            "command_id": cid,
            "outcome": "rejected",
            "reason": "not_running",
            "replayed": False,
            "snapshot": SNAPSHOT,
        }
    )
    assert r.reason == "not_running"
    assert SnapshotMessage.model_validate({"event": "snapshot", "data": SNAPSHOT})
    assert HeartbeatMessage.model_validate({"event": "heartbeat", "data": {"server_time_ms": 1}})


def test_openapi_json_is_up_to_date():
    assert OUT.exists(), "run: uv run python -m scripts.export_openapi"
    assert OUT.read_text() == render(), "contracts/openapi.json is stale; re-export and commit it"


# Endpoints the server has but contracts/openapi.json doesn't describe yet. Shrink, never grow.
KNOWN_MISSING_FROM_CONTRACT = {
    ("POST", "/api/rooms/{room_id}/bathroom"),
    ("POST", "/api/rooms/{room_id}/bathroom/{visit_id}/return"),
}


def test_every_server_endpoint_is_in_the_contract():
    from app.main import app
    from app.protocol.schema_app import build_schema_app

    def paths(a):
        spec = a.openapi()["paths"]
        return {(m.upper(), p) for p, ops in spec.items() if p.startswith("/api") for m in ops}

    real, contract = paths(app), paths(build_schema_app())
    assert real - contract == KNOWN_MISSING_FROM_CONTRACT, "add the endpoint to schema_app.py"
    assert contract <= real, "the contract describes an endpoint the server doesn't have"
