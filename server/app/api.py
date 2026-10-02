"""Slice 1 HTTP API: time, auth, snapshots, commands (docs/protocol.md §3-§7, polling only)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from app.protocol.constants import (
    CLIENT_HEADER,
    COOKIE_NAMES,
    MAX_STAFF_ROOMS,
    STAFF_SESSION_TTL_H,
)
from app.protocol.models import (
    ActorKind,
    Command,
    CommandResponse,
    CreateRoomRequest,
    LoginOptionsResponse,
    LoginRoomOption,
    ResetRoomRequest,
    RoomIdentity,
    RoomLoginRequest,
    RoomPresence,
    RoomSnapshot,
    StaffIdentity,
    StaffLoginRequest,
    StaffRole,
    StaffRoomsResponse,
    TimeResponse,
    UpdateRoomRequest,
)
from app.store import Session, Store, now_ms
from app.stream import frames

store = Store()
router = APIRouter(prefix="/api")


def err(status: int, code: str, msg: str) -> HTTPException:
    return HTTPException(status, {"error": code, "message": msg})


def require_client_header(request: Request) -> None:
    if not request.headers.get(CLIENT_HEADER):
        raise err(400, "invalid_request", f"missing {CLIENT_HEADER} header")


Post = Annotated[None, Depends(require_client_header)]


def session_for(request: Request, *surfaces: str) -> Session | None:
    for s in surfaces:
        tok = request.cookies.get(COOKIE_NAMES[s])
        if tok and tok in store.sessions and store.sessions[tok].surface == s:
            return store.sessions[tok]
    return None


def set_cookie(resp: Response, surface: str, token: str) -> None:
    resp.set_cookie(
        COOKIE_NAMES[surface],
        token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=STAFF_SESSION_TTL_H * 3600,
        path="/",
    )


@router.get("/time", response_model=TimeResponse)
async def get_time() -> TimeResponse:
    return TimeResponse(server_time_ms=now_ms())


@router.get("/auth/rooms", response_model=LoginOptionsResponse)
async def login_rooms(practice: bool = False) -> LoginOptionsResponse:
    rooms = sorted((r for r in store.rooms.values() if not r.deleted), key=lambda r: r.name)
    return LoginOptionsResponse(
        event_id=store.event_id,
        event_name=store.event_name,
        rooms=[LoginRoomOption(room_id=r.room_id, name=r.name) for r in rooms],
    )


@router.post("/auth/room-login", response_model=RoomIdentity)
async def room_login(body: RoomLoginRequest, response: Response, _: Post) -> RoomIdentity:
    room = store.rooms.get(body.room_id)
    if not room or room.deleted or not store.check_password(body.password, "ROOM_PASSWORD"):
        raise err(401, "invalid_credentials", "Wrong password for this room.")
    tok = store.new_session(Session("room", body.surface, room.room_id))
    set_cookie(response, body.surface, tok)
    return RoomIdentity(
        kind="room",
        room_id=room.room_id,
        room_name=room.name,
        surface=body.surface,
        event_id=store.event_id,
    )


@router.post("/auth/staff-login", response_model=StaffIdentity)
async def staff_login(body: StaffLoginRequest, response: Response, _: Post) -> StaffIdentity:
    if body.username != "admin" or not store.check_password(body.password, "ADMIN_PASSWORD"):
        raise err(401, "invalid_credentials", "Wrong password.")
    tok = store.new_session(Session("staff", "staff", role=StaffRole.ADMIN))
    set_cookie(response, "staff", tok)
    return StaffIdentity(kind="staff", account_id="admin", username="admin", role=StaffRole.ADMIN)


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, surface: str, _: Post) -> Response:
    if surface not in COOKIE_NAMES:
        raise err(422, "invalid_request", "unknown surface")
    tok = request.cookies.get(COOKIE_NAMES[surface])
    store.sessions.pop(tok or "", None)
    resp = Response(status_code=204)
    resp.delete_cookie(COOKIE_NAMES[surface], path="/")
    return resp


@router.get("/me", response_model=RoomIdentity | StaffIdentity)
async def me(request: Request, surface: str) -> RoomIdentity | StaffIdentity:
    if surface not in COOKIE_NAMES:
        raise err(422, "invalid_request", "unknown surface")
    s = session_for(request, surface)
    if not s:
        raise err(401, "unauthenticated", "Not logged in.")
    if s.kind == "staff":
        return StaffIdentity(
            kind="staff", account_id="admin", username="admin", role=s.role or StaffRole.ADMIN
        )
    room = store.rooms[s.room_id or ""]
    return RoomIdentity(
        kind="room",
        room_id=room.room_id,
        room_name=room.name,
        surface=surface,  # type: ignore[arg-type]
        event_id=store.event_id,
    )


def can_read(s: Session | None, room_id: str) -> bool:
    return bool(s) and (s.kind == "staff" or s.room_id == room_id)  # type: ignore[union-attr]


@router.get("/rooms/{room_id}/snapshot", response_model=RoomSnapshot)
async def snapshot(request: Request, room_id: str, since_version: int = -1) -> Response:
    room = store.rooms.get(room_id)
    if not room or room.deleted:
        raise err(404, "unknown_room", "No such room.")
    if not can_read(session_for(request, "staff", "control", "display"), room_id):
        raise err(401, "unauthenticated", "Not logged in.")
    if room.version <= since_version:
        return Response(status_code=304)
    return JSONResponse(store.snapshot(room).model_dump(mode="json"))


def sse(room_id: str | None, surface: str | None = None) -> StreamingResponse:
    return StreamingResponse(
        frames(store, room_id, surface=surface),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/rooms/{room_id}/stream")
async def room_stream(
    request: Request, room_id: str, surface: Literal["control", "display"] | None = None
) -> StreamingResponse:
    """`surface` says which page is listening, so staff can see who is connected. It only counts
    if that surface's own login is valid for this room (a staff preview never counts)."""
    room = store.rooms.get(room_id)
    if not room or room.deleted:
        raise err(404, "unknown_room", "No such room.")
    if not can_read(session_for(request, "staff", "control", "display"), room_id):
        raise err(401, "unauthenticated", "Not logged in.")
    counted = surface if surface and can_read(session_for(request, surface), room_id) else None
    return sse(room_id, counted)


@router.get("/staff/stream")
async def staff_stream(request: Request) -> StreamingResponse:
    if not session_for(request, "staff"):
        raise err(401, "unauthenticated", "Staff login required.")
    return sse(None)


@router.get("/staff/rooms", response_model=StaffRoomsResponse)
async def staff_rooms(request: Request) -> StaffRoomsResponse:
    if not session_for(request, "staff"):
        raise err(401, "unauthenticated", "Staff login required.")
    rooms = sorted(store.rooms.values(), key=lambda r: r.name)
    return StaffRoomsResponse(
        rooms=[store.snapshot(r) for r in rooms],
        presence=[RoomPresence(**p) for p in store.hub.presence_all()],
    )


@router.post("/staff/rooms", response_model=RoomSnapshot, status_code=201)
async def create_room(body: CreateRoomRequest, request: Request, _: Post) -> RoomSnapshot:
    staff = session_for(request, "staff")
    if not staff:
        raise err(401, "unauthenticated", "Staff login required.")
    if staff.role not in (StaffRole.ADMIN, StaffRole.PM):
        raise err(403, "forbidden", "Not allowed.")
    if len(store.rooms) >= MAX_STAFF_ROOMS:
        raise err(409, "too_many_rooms", "Room limit reached.")
    try:
        room = await store.create_room(body.name, body.duration_min, body.test_name, body.doc_url)
    except ValueError:
        raise err(422, "invalid_request", "Room name needs letters or numbers.") from None
    except KeyError:
        raise err(409, "room_exists", "A room with that name already exists.") from None
    return store.snapshot(room)


def admin_room(request: Request, room_id: str):
    """Staff (admin/PM) login required; returns the room (deleted rooms included)."""
    staff = session_for(request, "staff")
    if not staff:
        raise err(401, "unauthenticated", "Staff login required.")
    if staff.role not in (StaffRole.ADMIN, StaffRole.PM):
        raise err(403, "forbidden", "Not allowed.")
    room = store.rooms.get(room_id)
    if not room:
        raise err(404, "unknown_room", "No such room.")
    return room


def deleted_error():
    return err(409, "room_deleted", "That room is deleted. Restore it first.")


@router.patch("/staff/rooms/{room_id}", response_model=RoomSnapshot)
async def update_room(
    room_id: str, body: UpdateRoomRequest, request: Request, _: Post
) -> RoomSnapshot:
    room = admin_room(request, room_id)
    try:
        await store.update_room(room, body.duration_min, body.test_name, body.name, body.doc_url)
    except PermissionError:
        raise err(
            409, "room_started", "The timer already started. Use +5 min to change the time."
        ) from None
    except LookupError:
        raise deleted_error() from None
    except ValueError:
        raise err(422, "invalid_request", "Room name needs letters or numbers.") from None
    except KeyError:
        raise err(409, "room_exists", "A room with that name already exists.") from None
    return store.snapshot(room)


@router.post("/staff/rooms/{room_id}/reset", response_model=RoomSnapshot)
async def reset_room(
    room_id: str, body: ResetRoomRequest, request: Request, _: Post
) -> RoomSnapshot:
    room = admin_room(request, room_id)
    try:
        await store.reset_room(room, body.session_id)
    except PermissionError:
        raise err(
            409, "not_resettable", "Pause the timer first. Only paused or finished rooms reset."
        ) from None
    except RuntimeError:
        raise err(409, "stale_session", "This room was already reset. Refreshing.") from None
    except LookupError:
        raise deleted_error() from None
    return store.snapshot(room)


@router.delete("/staff/rooms/{room_id}", response_model=RoomSnapshot)
async def delete_room(room_id: str, request: Request, _: Post) -> RoomSnapshot:
    room = admin_room(request, room_id)
    try:
        await store.delete_room(room)
    except PermissionError:
        raise err(
            409, "room_in_progress", "A timer is in progress here. Finish or reset it first."
        ) from None
    return store.snapshot(room)


@router.post("/staff/rooms/{room_id}/restore", response_model=RoomSnapshot)
async def restore_room(room_id: str, request: Request, _: Post) -> RoomSnapshot:
    room = admin_room(request, room_id)
    await store.restore_room(room)
    return store.snapshot(room)


@router.post("/commands", response_model=CommandResponse)
async def commands(cmd: Command, request: Request, _: Post) -> CommandResponse:
    staff = session_for(request, "staff")
    room_sess = session_for(request, "control")
    room = store.rooms.get(cmd.room_id)
    if not room or room.deleted:
        raise err(404, "unknown_room", "No such room.")
    if staff and staff.role in (StaffRole.ADMIN, StaffRole.PM):
        allowed, actor = {"permit", "start", "pause", "resume", "end", "adjust"}, ActorKind.STAFF
    elif room_sess and room_sess.room_id == room.room_id:
        allowed, actor = {"start", "pause", "resume"}, ActorKind.ROOM
    else:
        raise err(403 if (staff or room_sess) else 401, "forbidden", "Not allowed.")
    if cmd.type not in allowed:
        raise err(403, "forbidden", f"'{cmd.type}' is not allowed for this login.")
    try:
        return await store.apply(room, cmd, actor)
    except ValueError:
        raise err(409, "command_id_conflict", "command_id reused with different content") from None
