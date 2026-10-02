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
