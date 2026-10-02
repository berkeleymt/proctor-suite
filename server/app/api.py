"""Slice 1 HTTP API: time, auth, snapshots, commands (docs/protocol.md §3-§7, polling only)."""

import asyncio
import os
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from app import google_auth
from app.protocol.constants import (
    CLIENT_HEADER,
    COOKIE_NAMES,
    MAX_STAFF_ROOMS,
    STAFF_SESSION_TTL_H,
    SUPER_COOKIE,
)
from app.protocol.models import (
    ActorKind,
    AddSuperAdminRequest,
    BathroomOutRequest,
    BrandResponse,
    ClarificationAdmin,
    ClarificationsResponse,
    Command,
    CommandResponse,
    CreateClarificationRequest,
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
    SuperAdminOut,
    SuperAdminsResponse,
    SuperConfig,
    SuperIdentity,
    SuperLoginRequest,
    SuperSettings,
    TimeResponse,
    UpdateClarificationRequest,
    UpdateRoomRequest,
    UpdateSettingsRequest,
)
from app.store import ClarError, Session, Store, now_ms
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
    if store.version(room) <= since_version:
        return Response(status_code=304)
    return JSONResponse(store.snapshot(room).model_dump(mode="json"))


def sse(
    room_id: str | None,
    surface: str | None = None,
    cid: str | None = None,
    clars: bool = False,
) -> StreamingResponse:
    return StreamingResponse(
        frames(store, room_id, surface=surface, cid=cid, clars=clars),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/rooms/{room_id}/stream")
async def room_stream(
    request: Request,
    room_id: str,
    surface: Literal["control", "display"] | None = None,
    cid: Annotated[str | None, Query(pattern=r"^[A-Za-z0-9_-]{8,64}$")] = None,
) -> StreamingResponse:
    """`surface` says which page is listening, so staff can see who is connected. It only counts
    if that surface's own login is valid for this room (a staff preview never counts)."""
    room = store.rooms.get(room_id)
    if not room or room.deleted:
        raise err(404, "unknown_room", "No such room.")
    if not can_read(session_for(request, "staff", "control", "display"), room_id):
        raise err(401, "unauthenticated", "Not logged in.")
    counted = surface if surface and can_read(session_for(request, surface), room_id) else None
    return sse(room_id, counted, cid)


@router.post("/rooms/{room_id}/stream/{cid}/close", status_code=204)
async def close_room_stream(room_id: str, cid: str, _: Post) -> Response:
    """A page is closing: drop its stream now so presence turns grey right away (0.5.0)."""
    store.hub.close(room_id, cid)
    return Response(status_code=204)


@router.get("/staff/stream")
async def staff_stream(request: Request, clarifications: bool = False) -> StreamingResponse:
    if not session_for(request, "staff"):
        raise err(401, "unauthenticated", "Staff login required.")
    return sse(None, clars=clarifications)


@router.get("/staff/rooms", response_model=StaffRoomsResponse)
async def staff_rooms(request: Request) -> StaffRoomsResponse:
    if not session_for(request, "staff"):
        raise err(401, "unauthenticated", "Staff login required.")
    rooms = sorted(store.rooms.values(), key=lambda r: r.name)
    return StaffRoomsResponse(
        rooms=[store.snapshot(r, with_clar=False) for r in rooms],
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


@router.post("/staff/rooms/{room_id}/empty", status_code=204)
async def empty_room(room_id: str, request: Request, _: Post) -> Response:
    """Wipe a deleted room and its history for good (0.8.0)."""
    room = admin_room(request, room_id)
    try:
        await store.empty_room(room)
    except PermissionError:
        raise err(409, "not_deleted", "Delete the room first, then empty it.") from None
    return Response(status_code=204)


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


# --- bathroom log (0.10.0) ---


def bathroom_room(request: Request, room_id: str):
    """The room's own proctor page, or an admin. Display pages cannot log students."""
    room = store.rooms.get(room_id)
    if not room or room.deleted:
        raise err(404, "unknown_room", "No such room.")
    staff = session_for(request, "staff")
    mine = session_for(request, "control")
    if not (
        (staff and staff.role in (StaffRole.ADMIN, StaffRole.PM))
        or (mine and mine.room_id == room_id)
    ):
        raise err(403 if (staff or mine) else 401, "forbidden", "Not allowed.")
    return room


@router.post("/rooms/{room_id}/bathroom", response_model=RoomSnapshot)
async def bathroom_out(
    room_id: str, body: BathroomOutRequest, request: Request, _: Post
) -> RoomSnapshot:
    room = bathroom_room(request, room_id)
    try:
        await store.bathroom_out(room, body.id, body.student_id)
    except ValueError:
        raise err(
            409, "id_conflict", "That request was already used for another student."
        ) from None
    except KeyError:
        raise err(409, "already_out", f"{body.student_id} is already out.") from None
    except OverflowError:
        raise err(
            409, "too_many_out", "Too many students are out. Mark some as back first."
        ) from None
    return store.snapshot(room)


@router.post("/rooms/{room_id}/bathroom/{visit_id}/return", response_model=RoomSnapshot)
async def bathroom_return(room_id: str, visit_id: UUID, request: Request, _: Post) -> RoomSnapshot:
    room = bathroom_room(request, room_id)
    try:
        await store.bathroom_return(room, visit_id)
    except KeyError:
        raise err(404, "unknown_visit", "No such entry.") from None
    return store.snapshot(room)


# --- clarifications (0.6.0) ---


def admin_only(request: Request) -> None:
    staff = session_for(request, "staff")
    if not staff:
        raise err(401, "unauthenticated", "Staff login required.")
    if staff.role not in (StaffRole.ADMIN, StaffRole.PM):
        raise err(403, "forbidden", "Not allowed.")


@router.get("/staff/clarifications", response_model=ClarificationsResponse)
async def list_clarifications(request: Request) -> ClarificationsResponse:
    admin_only(request)
    return ClarificationsResponse(clarifications=store.clarifications_admin())


@router.post("/staff/clarifications", response_model=ClarificationAdmin, status_code=201)
async def post_clarification(
    body: CreateClarificationRequest, request: Request, _: Post
) -> ClarificationAdmin:
    admin_only(request)
    try:
        x = await store.post_clarification(body.body, body.room_ids)
    except ValueError:
        raise err(422, "invalid_request", "Write something first.") from None
    except KeyError:
        raise err(422, "unknown_room", "One of those rooms doesn't exist.") from None
    return x.admin()


CLAR_ERRORS = {
    "empty": "Write something first.",
    "unknown_room": "That room doesn't exist.",
    "not_in_room": "This clarification isn't posted to that room.",
    "edit_limit": "This clarification has been edited too many times. Post a new one instead.",
    "deleted": "That clarification is deleted. Restore it first.",
    "not_deleted": "Delete it first, then empty it.",
}


@router.patch("/staff/clarifications/{clarification_id}", response_model=ClarificationAdmin)
async def update_clarification(
    clarification_id: UUID, body: UpdateClarificationRequest, request: Request, _: Post
) -> ClarificationAdmin:
    """Edit (body) or hide/unhide (hidden, optionally for one room_id)."""
    admin_only(request)
    try:
        if body.body is not None:
            x = await store.edit_clarification(clarification_id, body.body, body.room_id)
        else:
            x = await store.hide_clarification(clarification_id, bool(body.hidden), body.room_id)
    except KeyError:
        raise err(404, "unknown_clarification", "No such clarification.") from None
    except ClarError as e:
        raise err(422, e.code, CLAR_ERRORS[e.code]) from None
    return x.admin()


@router.delete("/staff/clarifications/{clarification_id}", status_code=204)
async def delete_clarification(
    clarification_id: UUID, request: Request, _: Post, room_id: str | None = None
) -> Response:
    """Delete (restorable) everywhere or from one room; "empty" wipes it for good."""
    admin_only(request)
    try:
        await store.delete_clarification(clarification_id, room_id)
    except KeyError:
        raise err(404, "unknown_clarification", "No such clarification.") from None
    except ClarError as e:
        raise err(422, e.code, CLAR_ERRORS[e.code]) from None
    return Response(status_code=204)


@router.post("/staff/clarifications/{clarification_id}/restore", response_model=ClarificationAdmin)
async def restore_clarification(
    clarification_id: UUID, request: Request, _: Post, room_id: str | None = None
) -> ClarificationAdmin:
    """Undo a delete, everywhere or (room_id) in one room (0.8.0)."""
    admin_only(request)
    try:
        x = await store.restore_clarification(clarification_id, room_id)
    except KeyError:
        raise err(404, "unknown_clarification", "No such clarification.") from None
    except ClarError as e:
        raise err(422, e.code, CLAR_ERRORS[e.code]) from None
    return x.admin()


@router.post("/staff/clarifications/{clarification_id}/empty", status_code=204)
async def empty_clarification(clarification_id: UUID, request: Request, _: Post) -> Response:
    """Wipe a deleted clarification from the database for good (0.8.0)."""
    admin_only(request)
    try:
        await store.empty_clarification(clarification_id)
    except KeyError:
        raise err(404, "unknown_clarification", "No such clarification.") from None
    except ClarError as e:
        raise err(422, e.code, CLAR_ERRORS[e.code]) from None
    return Response(status_code=204)


# --- branding and the super-admin page (0.9.0) ---


@router.get("/brand", response_model=BrandResponse)
async def brand() -> BrandResponse:
    name, icon = store.brand()
    return BrandResponse(name=name, icon=icon)


@router.get("/auth/super-config", response_model=SuperConfig)
async def super_config() -> SuperConfig:
    return SuperConfig(google_client_id=os.environ.get("GOOGLE_CLIENT_ID") or None)


def super_session(request: Request) -> Session | None:
    s = store.sessions.get(request.cookies.get(SUPER_COOKIE) or "")
    return s if s and s.kind == "super" and s.email and store.is_super(s.email) else None


def super_only(request: Request) -> Session:
    s = super_session(request)
    if not s:
        raise err(401, "unauthenticated", "Sign in with Google first.")
    return s


@router.post("/auth/super-login", response_model=SuperIdentity)
async def super_login(body: SuperLoginRequest, response: Response, _: Post) -> SuperIdentity:
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    if not client_id:
        raise err(503, "not_configured", "Google sign-in isn't set up on this server yet.")
    try:  # one HTTPS call to Google (their keys); keep it off the event loop
        claims = await asyncio.to_thread(google_auth.verify, body.credential, client_id)
    except ValueError:
        raise err(401, "invalid_credentials", "Google couldn't confirm that sign-in.") from None
    email = str(claims.get("email", "")).lower()
    if not email or claims.get("email_verified") is not True or not store.is_super(email):
        raise err(403, "not_allowed", f"{email or 'That account'} isn't a super-admin.")
    tok = store.new_session(Session("super", "super", email=email))
    response.set_cookie(
        SUPER_COOKIE, tok, httponly=True, secure=True, samesite="lax",
        max_age=STAFF_SESSION_TTL_H * 3600, path="/",
    )  # fmt: skip
    return SuperIdentity(email=email)


@router.post("/auth/super-logout", status_code=204)
async def super_logout(request: Request, _: Post) -> Response:
    store.sessions.pop(request.cookies.get(SUPER_COOKIE) or "", None)
    resp = Response(status_code=204)
    resp.delete_cookie(SUPER_COOKIE, path="/")
    return resp


@router.get("/super/me", response_model=SuperIdentity)
async def super_me(request: Request) -> SuperIdentity:
    return SuperIdentity(email=super_only(request).email or "")


def settings_out() -> SuperSettings:
    name, _icon = store.brand()
    return SuperSettings(
        app_name=name,
        app_icon=store.setting("APP_ICON"),
        room_password=store.setting("ROOM_PASSWORD"),
        admin_password=store.setting("ADMIN_PASSWORD"),
    )


@router.get("/super/settings", response_model=SuperSettings)
async def super_settings(request: Request) -> Response:
    super_only(request)
    return JSONResponse(settings_out().model_dump(), headers={"Cache-Control": "no-store"})


@router.patch("/super/settings", response_model=SuperSettings)
async def update_settings(body: UpdateSettingsRequest, request: Request, _: Post) -> Response:
    who = super_only(request).email or ""
    names = {
        "app_name": "APP_NAME",
        "app_icon": "APP_ICON",
        "room_password": "ROOM_PASSWORD",
        "admin_password": "ADMIN_PASSWORD",
    }
    changes = {}
    for field, env in names.items():
        value = getattr(body, field)
        if value is not None:
            changes[env] = value.strip() if field in ("app_name", "app_icon") else value
    changes = {k: v for k, v in changes.items() if v != store.setting(k)}
    revoke: set[str] = set()
    if body.log_out_old:
        revoke |= {"room"} if "ROOM_PASSWORD" in changes else set()
        revoke |= {"staff"} if "ADMIN_PASSWORD" in changes else set()
    if changes:
        await store.update_settings(changes, who, revoke)
    return JSONResponse(settings_out().model_dump(), headers={"Cache-Control": "no-store"})


def admins_out() -> SuperAdminsResponse:
    env = [
        SuperAdminOut(email=e, source="env", added_by=None, added_at_ms=None)
        for e in sorted(store.env_supers())
    ]
    added = [
        SuperAdminOut(email=a.email, source="added", added_by=a.added_by, added_at_ms=a.added_at_ms)
        for a in sorted(store.supers.values(), key=lambda a: (a.added_at_ms, a.email))
        if a.email not in store.env_supers()
    ]
    return SuperAdminsResponse(admins=env + added)


@router.get("/super/admins", response_model=SuperAdminsResponse)
async def list_super_admins(request: Request) -> SuperAdminsResponse:
    super_only(request)
    return admins_out()


@router.post("/super/admins", response_model=SuperAdminsResponse, status_code=201)
async def add_super_admin(
    body: AddSuperAdminRequest, request: Request, _: Post
) -> SuperAdminsResponse:
    who = super_only(request).email or ""
    try:
        await store.add_super(body.email, who)
    except ValueError:
        raise err(409, "already_super_admin", f"{body.email} is already a super-admin.") from None
    return admins_out()


@router.delete("/super/admins/{email}", response_model=SuperAdminsResponse)
async def remove_super_admin(email: str, request: Request, _: Post) -> SuperAdminsResponse:
    me = super_only(request).email
    email = email.strip().lower()
    if email == me:
        raise err(422, "cannot_remove_self", "You can't remove yourself. Ask another super-admin.")
    if email in store.env_supers():
        raise err(
            422, "set_in_env", "This one comes from SUPER_ADMIN_EMAILS in .env. Edit it there."
        )
    try:
        await store.remove_super(email)
    except KeyError:
        raise err(404, "unknown_admin", "No such super-admin.") from None
    return admins_out()
