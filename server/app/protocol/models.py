"""Wire models for protocol v0. The prose version is docs/protocol.md.

Rules for this file:
- Response models have NO field defaults (nullable fields are required-but-nullable), so the
  generated TypeScript types come out strict.
- Request models forbid extra fields, so typos fail loudly.
- JSON is snake_case. Times are integer milliseconds of server time (epoch ms).
- After editing, run `uv run python -m scripts.export_openapi` and commit contracts/openapi.json.
"""

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.protocol.constants import MAX_LOGIN_ROOMS, MAX_STAFF_ROOMS

# ---------------------------------------------------------------- enums


class TimerStatus(StrEnum):
    NOT_PERMITTED = "NOT_PERMITTED"
    PERMITTED = "PERMITTED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    ENDED = "ENDED"


class EventType(StrEnum):
    """Event types in a session's append-only list (plan §3.3)."""

    PERMIT = "PERMIT"
    START = "START"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    ADJUST = "ADJUST"
    END = "END"


class ActorKind(StrEnum):
    ROOM = "room"  # a proctor device; effective time = claimed_at_ms
    STAFF = "staff"  # Admin/PM; effective time = server receive time
    SYSTEM = "system"  # server-written markers (e.g. expiry); ignored by the fold


class RejectionReason(StrEnum):
    """Why an event was recorded but not applied. Only the fold produces these."""

    CLAIMED_AT_OUT_OF_BOUNDS = "claimed_at_out_of_bounds"
    SESSION_ENDED = "session_ended"
    ALREADY_PERMITTED = "already_permitted"
    NOT_PERMITTED = "not_permitted"
    ALREADY_STARTED = "already_started"
    NOT_RUNNING = "not_running"
    NOT_PAUSED = "not_paused"
    NOT_STARTED = "not_started"
    ADJUST_OUT_OF_RANGE = "adjust_out_of_range"
    STALE_SESSION = "stale_session"  # command targeted a session that is no longer current


class CommandOutcome(StrEnum):
    APPLIED = "applied"
    REJECTED = "rejected"


class ErrorCode(StrEnum):
    """HTTP-level errors. These are NOT recorded as events (see docs/protocol.md §6.5)."""

    INVALID_REQUEST = "invalid_request"  # 422 (also 400 for a missing client header)
    INVALID_CREDENTIALS = "invalid_credentials"  # 401, login only
    UNAUTHENTICATED = "unauthenticated"  # 401
    FORBIDDEN = "forbidden"  # 403: role or room mismatch
    UNKNOWN_ROOM = "unknown_room"  # 404
    UNKNOWN_SESSION = "unknown_session"  # 404
    COMMAND_ID_CONFLICT = "command_id_conflict"  # 409: same command_id, different content
    RATE_LIMITED = "rate_limited"  # 429
    UNAVAILABLE = "unavailable"  # 503
    INTERNAL = "internal"  # 500


class StaffRole(StrEnum):
    ADMIN = "admin"
    PM = "pm"
    TO = "to"


class Surface(StrEnum):
    DISPLAY = "display"
    CONTROL = "control"
    STAFF = "staff"


# ---------------------------------------------------------------- snapshots


class TimerSnapshot(BaseModel):
    """The folded timer state (plan §3.3).

    remaining(now) = max(0, duration_ms + adjust_total_ms - elapsed_banked_ms
                            - (now - running_since_ms if RUNNING else 0))
    """

    status: TimerStatus
    duration_ms: int
    adjust_total_ms: int
    elapsed_banked_ms: int
    running_since_ms: int | None


class RoomSnapshot(BaseModel):
    """Everything a room device needs to show and tick the timer. Sent in full every time."""

    room_id: str
    room_name: str
    test_name: str
    session_id: str
    version: int  # per room; increases whenever the room's snapshot changes
    server_time_ms: int  # informational only; NOT a clock-sync sample
    timer: TimerSnapshot


# ---------------------------------------------------------------- commands


class _CommandBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID  # client-generated; the server applies each id at most once (invariant 3)
    device_id: UUID  # stable per browser install
    room_id: str = Field(min_length=1, max_length=64)
    session_id: str = Field(
        min_length=1, max_length=64
    )  # the session the client believes is current
    claimed_at_ms: int  # client's best estimate of server time (serverNow()); ignored for staff
    proctor_name: str | None = Field(default=None, max_length=100)
    reason: str | None = Field(default=None, max_length=200)


class PermitCommand(_CommandBase):
    type: Literal["permit"]


class StartCommand(_CommandBase):
    type: Literal["start"]


class PauseCommand(_CommandBase):
    type: Literal["pause"]


class ResumeCommand(_CommandBase):
    type: Literal["resume"]


class EndCommand(_CommandBase):
    type: Literal["end"]


class AdjustCommand(_CommandBase):
    type: Literal["adjust"]
    # Deliberately unbounded here: out-of-range values are recorded as a rejected event
    # (adjust_out_of_range) so the audit log shows the attempt.
    delta_ms: int


Command = Annotated[
    PermitCommand | StartCommand | PauseCommand | ResumeCommand | EndCommand | AdjustCommand,
    Field(discriminator="type"),
]


class CommandResponse(BaseModel):
    command_id: UUID
    outcome: CommandOutcome
    reason: RejectionReason | None
    replayed: bool  # true if this command_id had already been processed
    snapshot: RoomSnapshot  # the room's current snapshot after processing


class ErrorResponse(BaseModel):
    error: ErrorCode
    message: str


# ---------------------------------------------------------------- time, auth


class TimeResponse(BaseModel):
    server_time_ms: int


class LoginRoomOption(BaseModel):
    room_id: str
    name: str


class LoginOptionsResponse(BaseModel):
    event_id: str
    event_name: str
    rooms: list[LoginRoomOption] = Field(max_length=MAX_LOGIN_ROOMS)


class RoomLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_id: str = Field(min_length=1, max_length=64)  # chosen in the dropdown: the "username"
    password: str = Field(min_length=1, max_length=200)
    surface: Literal["display", "control"]


class StaffLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class RoomIdentity(BaseModel):
    kind: Literal["room"]
    room_id: str
    room_name: str
    surface: Literal["display", "control"]
    event_id: str


class StaffIdentity(BaseModel):
    kind: Literal["staff"]
    account_id: str
    username: str
    role: StaffRole


Identity = Annotated[RoomIdentity | StaffIdentity, Field(discriminator="kind")]


class StaffRoomsResponse(BaseModel):
    rooms: list[RoomSnapshot] = Field(max_length=MAX_STAFF_ROOMS)


class CreateRoomRequest(BaseModel):
    """Admin adds a room (wireframe: Admin · Timers). Duration defaults to 180 minutes."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=60)
    duration_min: int = Field(default=180, ge=1, le=720)


# ---------------------------------------------------------------- SSE messages


class Heartbeat(BaseModel):
    server_time_ms: int


class SnapshotMessage(BaseModel):
    """SSE frame: `event: snapshot`, `id: <version>`, `data: <RoomSnapshot as JSON>`."""

    event: Literal["snapshot"]
    data: RoomSnapshot


class HeartbeatMessage(BaseModel):
    """SSE frame: `event: heartbeat`, `data: <Heartbeat as JSON>`."""

    event: Literal["heartbeat"]
    data: Heartbeat


# Models that no route references directly but that are part of the contract.
EXTRA_SCHEMA_MODELS: list[type[BaseModel]] = [SnapshotMessage, HeartbeatMessage, Heartbeat]
