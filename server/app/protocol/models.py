"""Wire models for protocol v0. The prose version is docs/protocol.md.

Rules for this file:
- Response models have NO field defaults (nullable fields are required-but-nullable), so the
  generated TypeScript types come out strict.
- Request models forbid extra fields, so typos fail loudly.
- JSON is snake_case. Times are integer milliseconds of server time (epoch ms).
- After editing, run `uv run python -m scripts.export_openapi` and commit contracts/openapi.json.
"""

import re
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.protocol.constants import (
    MAX_ADMIN_BATHROOM_EXPORT,
    MAX_BATHROOM_BACK,
    MAX_BATHROOM_IDS,
    MAX_BATHROOM_OUT,
    MAX_LOGIN_ROOMS,
    MAX_ROSTER_ROWS,
    MAX_STAFF_ROOMS,
)

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


class ClarificationOut(BaseModel):
    """One visible clarification, as a room device sees it."""

    id: UUID
    body: str  # Markdown with $math$ / $$math$$ (0.7.0); lines starting "- " are bullets
    created_at_ms: int
    # Earlier wordings, oldest first. Students see them struck out above `body`, so an edit
    # is never silent (0.7.0). At most MAX_CLARIFICATION_EDITS.
    previous: list[str]
    edited_at_ms: int | None


class ClarificationAdmin(ClarificationOut):
    room_ids: list[str] | None  # null = all rooms
    hidden: bool  # hidden everywhere
    hidden_room_ids: list[str]  # hidden only in these rooms (0.7.0)
    # Deleted from only these rooms (0.7.0). Restorable until the clarification is emptied (0.8.0).
    removed_room_ids: list[str]
    deleted: bool  # deleted everywhere, restorable; only "empty" wipes the row (0.8.0)
    # Rooms that got their own edited copy; they no longer show this one (0.8.0).
    edited_room_ids: list[str]


class ClarificationsResponse(BaseModel):
    clarifications: list[ClarificationAdmin]  # newest first, at most 200, hidden included


class CreateClarificationRequest(BaseModel):
    """Admin posts a clarification (wireframe: Admin · Clarifications). null room_ids = all."""

    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=2000)
    room_ids: list[str] | None = Field(default=None, min_length=1, max_length=500)


class UpdateClarificationRequest(BaseModel):
    """Exactly one of `hidden` (hide/unhide) or `body` (edit; the old wording stays visible,
    struck out). `room_id` limits the action to one room. A per-room edit moves that room to
    a new copy with the edited text and returns the copy (0.8.0)."""

    model_config = ConfigDict(extra="forbid")
    hidden: bool | None = None
    body: str | None = Field(default=None, min_length=1, max_length=2000)
    room_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def _one_action(self):
        if (self.hidden is None) == (self.body is None):
            raise ValueError("send exactly one of hidden or body")
        return self


class BathroomVisit(BaseModel):
    """One student leaving the room. `back_ms` is null while they are out. Times are server time."""

    id: UUID
    student_id: str
    student_name: str | None  # from the roster, when there is one (0.11.0)
    left_ms: int
    back_ms: int | None


class BathroomOutRequest(BaseModel):
    id: UUID  # client-generated, so a retry never logs the student twice (invariant 3)
    student_id: str

    @model_validator(mode="after")
    def _clean(self):
        self.student_id = " ".join(self.student_id.split()).upper()
        if not 1 <= len(self.student_id) <= 20:
            raise ValueError("Enter the student's ID (up to 20 characters).")
        return self


class RoomSnapshot(BaseModel):
    """Everything a room device needs to show and tick the timer. Sent in full every time."""

    room_id: str
    room_name: str
    test_name: str
    session_id: str
    version: int  # per room; increases whenever the room's snapshot changes
    server_time_ms: int  # informational only; NOT a clock-sync sample
    timer: TimerSnapshot
    deleted: bool  # soft-deleted by an admin; only staff ever see these
    doc_url: str | None  # optional https link (clarifications doc), set by an admin
    # Visible clarifications for this room, oldest first, at most 50. Always [] in the staff
    # room list and staff stream (staff read /api/staff/clarifications instead).
    clarifications: list[ClarificationOut]
    # Bathroom log (0.10.0). `students_out` is always right; the two lists are only filled for
    # the room's own devices and the staff stream/list sends []. Bounded (invariant 8).
    students_out: int = Field(ge=0)
    bathroom_out: list[BathroomVisit] = Field(max_length=MAX_BATHROOM_OUT)
    bathroom_back: list[BathroomVisit] = Field(max_length=MAX_BATHROOM_BACK)


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


# ------------------------------------------------- branding and super-admin (0.9.0)

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class BrandResponse(BaseModel):
    """Public: what every page shows as its title and icon. Empty strings if not configured."""

    name: str
    icon: str  # absolute URL, or a path from the site root; "" = no icon


class SuperConfig(BaseModel):
    """Public: what the sign-in button needs. null = Google sign-in is not set up on this server."""

    google_client_id: str | None


class SuperLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    credential: str = Field(min_length=20, max_length=4096)  # Google ID token (a JWT)


class SuperIdentity(BaseModel):
    email: str


class SuperSettings(BaseModel):
    """What the super-admin page edits. These replace the same-named .env values at runtime."""

    app_name: str
    app_icon: str
    room_password: str
    admin_password: str


def _icon_ok(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip()
    if v and "://" in v and not v.startswith(("https://", "http://")):
        raise ValueError("icon must be a path or an http(s) URL")
    if v and "://" not in v and not re.fullmatch(r"[\w./-]+", v):
        raise ValueError("icon path may only use letters, digits, / . _ -")
    return v


class UpdateSettingsRequest(BaseModel):
    """Omitted fields are unchanged. `log_out_old` signs out everyone who got in with a password
    that this request changes (room devices for the room password, admins for the admin one)."""

    model_config = ConfigDict(extra="forbid")
    app_name: str | None = Field(default=None, min_length=1, max_length=40)
    app_icon: str | None = Field(default=None, max_length=500)  # "" removes the icon
    room_password: str | None = Field(default=None, min_length=8, max_length=100)
    admin_password: str | None = Field(default=None, min_length=8, max_length=100)
    log_out_old: bool = False

    _check_icon = field_validator("app_icon")(_icon_ok)

    @field_validator("app_name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name can't be blank")
        return v


class SuperAdminOut(BaseModel):
    email: str
    source: Literal["env", "added"]  # "env" = SUPER_ADMIN_EMAILS in .env: cannot be removed here
    added_by: str | None
    added_at_ms: int | None


class SuperAdminsResponse(BaseModel):
    admins: list[SuperAdminOut]


class AddSuperAdminRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=254)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL.match(v):
            raise ValueError("not an email address")
        return v


class SurfacePresence(BaseModel):
    online: int = Field(ge=0)  # open streams from that page right now
    last_seen_ms: int | None = (
        None  # last connect/disconnect; null = never since the server started
    )


class RoomPresence(BaseModel):
    """Who has this room's pages open (staff stream only). `control` = proctor page."""

    room_id: str
    control: SurfacePresence
    display: SurfacePresence


class StaffRoomsResponse(BaseModel):
    rooms: list[RoomSnapshot] = Field(max_length=MAX_STAFF_ROOMS)
    presence: list[RoomPresence] = Field(default_factory=list, max_length=MAX_STAFF_ROOMS)


def _https_url(v: str | None) -> str | None:
    """Empty string clears; anything else must be an https link."""
    if v is None:
        return None
    v = v.strip()
    if v and not v.startswith("https://"):
        raise ValueError("Use a link that starts with https://")
    return v


class CreateRoomRequest(BaseModel):
    """Admin adds a room (wireframe: Admin · Timers). Duration defaults to 180 minutes."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=60)
    duration_min: int = Field(default=180, ge=1, le=720)
    test_name: str | None = Field(default=None, max_length=60)
    doc_url: str | None = Field(default=None, max_length=500)

    _check_url = field_validator("doc_url")(_https_url)


class UpdateRoomRequest(BaseModel):
    """Admin edits a room that has not started (wireframe: Edit…). Omitted fields are unchanged.

    Duration can only change before the timer starts; use `adjust` (+/- time) once running.
    """

    model_config = ConfigDict(extra="forbid")
    duration_min: int | None = Field(default=None, ge=1, le=720)
    test_name: str | None = Field(default=None, min_length=1, max_length=60)
    name: str | None = Field(default=None, min_length=1, max_length=60)
    doc_url: str | None = Field(default=None, max_length=500)  # "" removes it

    _check_url = field_validator("doc_url")(_https_url)


class ResetRoomRequest(BaseModel):
    """Admin resets a paused or finished room to a fresh, not-started timer. `session_id` is the
    session the admin was looking at, so two admins can't reset twice by accident."""

    model_config = ConfigDict(extra="forbid")
    session_id: str


# ---------------------------------------------------------------- SSE messages


class Heartbeat(BaseModel):
    server_time_ms: int


class SnapshotMessage(BaseModel):
    """SSE frame: `event: snapshot`, `id: <version>`, `data: <RoomSnapshot as JSON>`."""

    event: Literal["snapshot"]
    data: RoomSnapshot


class PresenceMessage(BaseModel):
    """SSE frame on the staff stream: `event: presence`, `data: <RoomPresence as JSON>`."""

    event: Literal["presence"]
    data: RoomPresence


class HeartbeatMessage(BaseModel):
    """SSE frame: `event: heartbeat`, `data: <Heartbeat as JSON>`."""

    event: Literal["heartbeat"]
    data: Heartbeat


# ---------------------------------------------------------------- bathroom (admin) and roster, 0.11.0


class BathroomEntry(BaseModel):
    """One bathroom record in the admin list. `deleted` ones are only listed on request."""

    id: UUID
    room_id: str
    room_name: str
    student_id: str
    student_name: str | None
    school: str | None
    left_ms: int
    back_ms: int | None
    deleted: bool


class BathroomLogResponse(BaseModel):
    """Counts are for everything; the list is cut to `limit` (`truncated`)."""

    entries: list[BathroomEntry] = Field(max_length=2 * MAX_ADMIN_BATHROOM_EXPORT)
    out_now: int = Field(ge=0)
    returned: int = Field(ge=0)
    deleted: int = Field(ge=0)
    truncated: bool
    server_time_ms: int


class BathroomActionRequest(BaseModel):
    """Delete (soft), restore, or empty (for good, deleted ones only). Exactly one of `ids`
    or `all`; `all` means every record the action applies to."""

    model_config = ConfigDict(extra="forbid")
    action: Literal["delete", "restore", "empty"]
    ids: list[UUID] | None = Field(default=None, max_length=MAX_BATHROOM_IDS)
    all: bool = False

    @model_validator(mode="after")
    def _one_target(self):
        if (self.ids is None) == (not self.all):
            raise ValueError("send exactly one of ids or all")
        return self


class BathroomActionResponse(BaseModel):
    changed: int = Field(ge=0)
    skipped: int = Field(ge=0)  # a restore that would put a student out twice in one room


class StudentInfo(BaseModel):
    """What a proctor may see about a student: no contact details."""

    id: str
    name: str
    school: str
    team: str
    room: str  # "" when unknown


class StudentLookup(BaseModel):
    roster_loaded: bool  # false = nothing imported yet, so "not found" means nothing
    student: StudentInfo | None


class RosterStudent(StudentInfo):
    contact: str
    out_since_ms: int | None  # set while the student is out in any room


class RosterResponse(BaseModel):
    students: list[RosterStudent] = Field(max_length=MAX_ROSTER_ROWS)
    total: int = Field(ge=0)  # students in the whole roster
    matching: int = Field(ge=0)  # students matching the room / search
    out_now: int = Field(ge=0)  # of the matching ones
    rooms: list[str]  # room names that appear in the roster, sorted
    synced_at_ms: int | None
    source: str | None  # "csv" or "contestdojo"
    sync_available: bool  # CONTESTDOJO_* is configured on the server


class RosterImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csv: str = Field(min_length=1, max_length=2_000_000)


class RosterImportResponse(BaseModel):
    count: int = Field(ge=0)
    notes: list[str] = Field(max_length=6)  # skipped rows, first few only


# Models that no route references directly but that are part of the contract.
EXTRA_SCHEMA_MODELS: list[type[BaseModel]] = [SnapshotMessage, HeartbeatMessage, Heartbeat]
