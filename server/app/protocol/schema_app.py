"""Builds the OpenAPI document for the contract (contracts/openapi.json).

This is a SCHEMA-ONLY app: the route functions are stubs and are never mounted in the real
server (app.main). When the real routers exist, the export script should switch to building
from them (and this file goes away); the contract test will fail if the two ever disagree.
"""

from typing import Annotated, Any, Literal

from fastapi import FastAPI, Path, Query, Response
from fastapi.openapi.utils import get_openapi

from app.protocol.constants import COOKIE_NAMES, PROTOCOL_VERSION
from app.protocol.models import (
    EXTRA_SCHEMA_MODELS,
    AddSuperAdminRequest,
    BathroomActionRequest,
    BathroomActionResponse,
    BathroomLogResponse,
    BrandResponse,
    ClarificationAdmin,
    ClarificationsResponse,
    Command,
    CommandResponse,
    CreateClarificationRequest,
    CreateRoomRequest,
    ErrorResponse,
    Identity,
    LoginOptionsResponse,
    ResetRoomRequest,
    RoomIdentity,
    RoomLoginRequest,
    RoomSnapshot,
    RosterImportResponse,
    RosterResponse,
    RosterRoomRequest,
    StaffIdentity,
    StaffLoginRequest,
    StaffRoomsResponse,
    StudentLookup,
    SuperAdminsResponse,
    SuperConfig,
    SuperIdentity,
    SuperLoginRequest,
    SuperSettings,
    Surface,
    TimeResponse,
    UpdateClarificationRequest,
    UpdateRoomRequest,
    UpdateSettingsRequest,
)

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "unauthenticated / invalid_credentials"},
    403: {"model": ErrorResponse, "description": "forbidden"},
    404: {"model": ErrorResponse, "description": "unknown_room / unknown_session"},
    422: {"model": ErrorResponse, "description": "invalid_request"},
    429: {"model": ErrorResponse, "description": "rate_limited"},
}

_SSE: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "text/event-stream. Frames are SnapshotMessage, HeartbeatMessage and (staff stream only) PresenceMessage.",
        "content": {
            "text/event-stream": {
                "schema": {
                    "oneOf": [
                        {"$ref": "#/components/schemas/SnapshotMessage"},
                        {"$ref": "#/components/schemas/HeartbeatMessage"},
                    ]
                }
            }
        },
    },
    **_ERRORS,
}


def _stub() -> None:
    raise NotImplementedError("schema-only route")


def build_schema_app() -> FastAPI:
    app = FastAPI(
        title="Proctor Suite protocol",
        version=PROTOCOL_VERSION,
        docs_url=None,
        redoc_url=None,
        separate_input_output_schemas=False,
        description="Contract for room devices and staff. Prose: docs/protocol.md.",
    )

    @app.get("/api/time", response_model=TimeResponse, tags=["time"])
    async def get_time():
        """Clock-sync probe. No auth. Never touches Postgres."""
        _stub()

    @app.get(
        "/api/auth/rooms", response_model=LoginOptionsResponse, tags=["auth"], responses=_ERRORS
    )
    async def login_options(practice: bool = False):
        """Rooms for the login dropdown. No auth. Bounded (MAX_LOGIN_ROOMS)."""
        _stub()

    @app.post("/api/auth/room-login", response_model=RoomIdentity, tags=["auth"], responses=_ERRORS)
    async def room_login(body: RoomLoginRequest):
        """Room name (dropdown) + event password. Sets display_sid or control_sid."""
        _stub()

    @app.post(
        "/api/auth/staff-login", response_model=StaffIdentity, tags=["auth"], responses=_ERRORS
    )
    async def staff_login(body: StaffLoginRequest):
        """Named staff account. Sets staff_sid."""
        _stub()

    @app.post("/api/auth/logout", status_code=204, tags=["auth"], responses=_ERRORS)
    async def logout(surface: Surface) -> Response:
        """Clears the cookie for one surface."""
        _stub()

    @app.get("/api/me", response_model=Identity, tags=["auth"], responses=_ERRORS)
    async def me(surface: Surface):
        """Who is logged in on this surface (cookies are HttpOnly, so the UI asks)."""
        _stub()

    @app.get(
        "/api/rooms/{room_id}/snapshot",
        response_model=RoomSnapshot,
        tags=["rooms"],
        responses={304: {"description": "Nothing newer than since_version"}, **_ERRORS},
    )
    async def room_snapshot(
        room_id: Annotated[str, Path()],
        since_version: Annotated[int | None, Query(ge=0)] = None,
    ):
        """Polling fallback. Served from memory. 304 when version <= since_version."""
        _stub()

    @app.get("/api/rooms/{room_id}/stream", tags=["rooms"], responses=_SSE)
    async def room_stream(
        room_id: Annotated[str, Path()],
        surface: Annotated[Literal["control", "display"] | None, Query()] = None,
        cid: Annotated[str | None, Query(pattern=r"^[A-Za-z0-9_-]{8,64}$")] = None,
    ):
        """SSE: current snapshot immediately, then every change, plus heartbeats.
        `cid` is a random id the page picks so it can end this stream early (0.5.0)."""
        _stub()

    @app.post(
        "/api/rooms/{room_id}/stream/{cid}/close",
        status_code=204,
        tags=["rooms"],
        responses=_ERRORS,
    )
    async def close_room_stream(room_id: str, cid: str):
        """A page is closing: end its stream now so presence updates at once. Needs X-Proctor-Client. 0.5.0."""
        _stub()

    @app.post("/api/commands", response_model=CommandResponse, tags=["commands"], responses=_ERRORS)
    async def post_command(body: Command):
        """One command, idempotent on command_id. Needs X-Proctor-Client."""
        _stub()

    @app.get(
        "/api/staff/rooms", response_model=StaffRoomsResponse, tags=["staff"], responses=_ERRORS
    )
    async def staff_rooms():
        """All rooms' snapshots (staff dashboard first load)."""
        _stub()

    @app.post(
        "/api/staff/rooms",
        response_model=RoomSnapshot,
        status_code=201,
        tags=["staff"],
        responses={**_ERRORS, 409: {"model": ErrorResponse, "description": "room_exists"}},
    )
    async def create_room(body: CreateRoomRequest):
        """Admin adds a room (name, duration_min default 180). Added in 0.2.0."""
        _stub()

    @app.patch(
        "/api/staff/rooms/{room_id}",
        response_model=RoomSnapshot,
        tags=["staff"],
        responses={**_ERRORS, 409: {"model": ErrorResponse, "description": "room_started"}},
    )
    async def update_room(room_id: str, body: UpdateRoomRequest):
        """Admin edits duration (before start only) and/or test label. Added in 0.3.0."""
        _stub()

    @app.post(
        "/api/staff/rooms/{room_id}/reset",
        response_model=RoomSnapshot,
        tags=["staff"],
        responses={
            **_ERRORS,
            409: {
                "model": ErrorResponse,
                "description": "not_resettable | stale_session | room_deleted",
            },
        },
    )
    async def reset_room(room_id: str, body: ResetRoomRequest):
        """Admin: fresh not-started timer for a PAUSED or ENDED room. Added in 0.4.0."""
        _stub()

    @app.delete(
        "/api/staff/rooms/{room_id}",
        response_model=RoomSnapshot,
        tags=["staff"],
        responses={**_ERRORS, 409: {"model": ErrorResponse, "description": "room_in_progress"}},
    )
    async def delete_room(room_id: str):
        """Admin: soft delete (hide). Not while RUNNING or PAUSED. Signs the room out. 0.4.0."""
        _stub()

    @app.post(
        "/api/staff/rooms/{room_id}/restore",
        response_model=RoomSnapshot,
        tags=["staff"],
        responses=_ERRORS,
    )
    async def restore_room(room_id: str):
        """Admin: undo a soft delete. Added in 0.4.0."""
        _stub()

    @app.get(
        "/api/staff/clarifications",
        response_model=ClarificationsResponse,
        tags=["staff"],
        responses=_ERRORS,
    )
    async def list_clarifications():
        """Admin: every clarification, newest first, hidden included. Added in 0.6.0."""
        _stub()

    @app.post(
        "/api/staff/clarifications",
        response_model=ClarificationAdmin,
        status_code=201,
        tags=["staff"],
        responses={**_ERRORS, 422: {"model": ErrorResponse, "description": "unknown_room"}},
    )
    async def post_clarification(body: CreateClarificationRequest):
        """Admin posts text to all rooms (room_ids null) or a subset. Added in 0.6.0."""
        _stub()

    @app.patch(
        "/api/staff/clarifications/{clarification_id}",
        response_model=ClarificationAdmin,
        tags=["staff"],
        responses={
            **_ERRORS,
            404: {"model": ErrorResponse, "description": "unknown_clarification"},
            422: {
                "model": ErrorResponse,
                "description": "empty, unknown_room, not_in_room, edit_limit, deleted",
            },
        },
    )
    async def update_clarification(clarification_id: str, body: UpdateClarificationRequest):
        """Admin edits (`body`; old wording stays, struck out) or hides/unhides (`hidden`, one
        room with `room_id`). Added in 0.6.0 as hide only; edit and per-room in 0.7.0. With
        `body` and `room_id` (0.8.0) that room moves to a new edited copy, which is returned."""
        _stub()

    @app.delete(
        "/api/staff/clarifications/{clarification_id}",
        status_code=204,
        tags=["staff"],
        responses={
            **_ERRORS,
            404: {"model": ErrorResponse, "description": "unknown_clarification"},
            422: {"model": ErrorResponse, "description": "unknown_room, not_in_room"},
        },
    )
    async def delete_clarification(clarification_id: str, room_id: str | None = None):
        """Admin deletes a clarification, or (`room_id`) from one room only. Soft since 0.8.0:
        restorable until emptied. Added in 0.7.0."""
        _stub()

    @app.post(
        "/api/staff/clarifications/{clarification_id}/restore",
        response_model=ClarificationAdmin,
        tags=["staff"],
        responses={
            **_ERRORS,
            404: {"model": ErrorResponse, "description": "unknown_clarification"},
            422: {"model": ErrorResponse, "description": "unknown_room, not_in_room"},
        },
    )
    async def restore_clarification(clarification_id: str, room_id: str | None = None):
        """Admin undoes a delete, everywhere or (`room_id`) in one room. Added in 0.8.0."""
        _stub()

    @app.post(
        "/api/staff/clarifications/{clarification_id}/empty",
        status_code=204,
        tags=["staff"],
        responses={
            **_ERRORS,
            404: {"model": ErrorResponse, "description": "unknown_clarification"},
            422: {"model": ErrorResponse, "description": "not_deleted"},
        },
    )
    async def empty_clarification(clarification_id: str):
        """Admin wipes a deleted clarification from the database for good. Added in 0.8.0."""
        _stub()

    @app.post(
        "/api/staff/rooms/{room_id}/empty",
        status_code=204,
        tags=["staff"],
        responses={
            **_ERRORS,
            409: {"model": ErrorResponse, "description": "not_deleted"},
        },
    )
    async def empty_room(room_id: str):
        """Admin wipes a deleted room and its history from the database for good. 0.8.0."""
        _stub()

    @app.get(
        "/api/staff/bathroom", response_model=BathroomLogResponse, tags=["staff"], responses=_ERRORS
    )
    async def staff_bathroom(
        status: Literal["out", "returned", "all"] = "out",
        room_id: str | None = None,
        q: str | None = None,
        deleted: bool = False,
        limit: int = 500,
    ):
        """Admin: bathroom records across rooms, newest first (longest out first for `out`).
        `deleted=true` adds the soft-deleted ones after the live ones. Added in 0.11.0."""
        _stub()

    @app.post(
        "/api/staff/bathroom/action",
        response_model=BathroomActionResponse,
        tags=["staff"],
        responses=_ERRORS,
    )
    async def staff_bathroom_action(body: BathroomActionRequest):
        """Admin only (proctors can record and view, never delete): soft delete, restore, or
        empty (permanent, deleted records only). 0.11.0."""
        _stub()

    @app.get("/api/staff/roster", response_model=RosterResponse, tags=["staff"], responses=_ERRORS)
    async def staff_roster(room: str | None = None, q: str | None = None):
        """Admin: the imported roster, filtered by room name (`room=` for no room) or search."""
        _stub()

    @app.post(
        "/api/staff/roster/sync",
        response_model=RosterImportResponse,
        tags=["staff"],
        responses={
            **_ERRORS,
            502: {"model": ErrorResponse, "description": "sync_failed"},
            503: {"model": ErrorResponse, "description": "not_configured"},
        },
    )
    async def staff_roster_sync():
        """Admin: replace the roster from ContestDojo's API, only when CONTESTDOJO_* is set."""
        _stub()

    @app.post(
        "/api/staff/roster/room",
        response_model=RosterImportResponse,
        tags=["staff"],
        responses=_ERRORS,
    )
    async def staff_roster_room(body: RosterRoomRequest):
        """Admin: set (empty = clear) the room of the given student IDs. `count` = students changed."""
        _stub()

    @app.post(
        "/api/staff/roster/clear",
        response_model=RosterImportResponse,
        tags=["staff"],
        responses=_ERRORS,
    )
    async def staff_roster_clear():
        """Admin: delete every roster row (privacy cleanup). `count` = students removed."""
        _stub()

    @app.get("/api/roster/lookup", response_model=StudentLookup, tags=["rooms"], responses=_ERRORS)
    async def roster_lookup(id: str):
        """A room's proctor or staff: one student by ID, from memory. No contact details."""
        _stub()

    @app.get("/api/brand", response_model=BrandResponse, tags=["public"])
    async def brand():
        """Public: the site name and icon every page shows. Added in 0.9.0."""
        _stub()

    @app.get("/api/auth/super-config", response_model=SuperConfig, tags=["super"])
    async def super_config():
        """Public: the Google client id for the sign-in button (null = not set up). 0.9.0."""
        _stub()

    @app.post(
        "/api/auth/super-login",
        response_model=SuperIdentity,
        tags=["super"],
        responses={
            401: {"model": ErrorResponse, "description": "invalid_credentials"},
            403: {"model": ErrorResponse, "description": "not_allowed"},
            503: {"model": ErrorResponse, "description": "not_configured"},
        },
    )
    async def super_login(body: SuperLoginRequest):
        """Sign in with a Google ID token. Only emails on the super-admin list get a session."""
        _stub()

    @app.post("/api/auth/super-logout", status_code=204, tags=["super"])
    async def super_logout():
        _stub()

    @app.get("/api/super/me", response_model=SuperIdentity, tags=["super"], responses=_ERRORS)
    async def super_me():
        _stub()

    @app.get("/api/super/settings", response_model=SuperSettings, tags=["super"], responses=_ERRORS)
    async def super_settings():
        """Super-admin: current name, icon and the two passwords (not cached)."""
        _stub()

    @app.patch(
        "/api/super/settings", response_model=SuperSettings, tags=["super"], responses=_ERRORS
    )
    async def update_settings(body: UpdateSettingsRequest):
        """Change any of them; they replace the .env values from now on. 0.9.0."""
        _stub()

    @app.get(
        "/api/super/admins", response_model=SuperAdminsResponse, tags=["super"], responses=_ERRORS
    )
    async def list_super_admins():
        _stub()

    @app.post(
        "/api/super/admins",
        response_model=SuperAdminsResponse,
        status_code=201,
        tags=["super"],
        responses={**_ERRORS, 409: {"model": ErrorResponse, "description": "already_super_admin"}},
    )
    async def add_super_admin(body: AddSuperAdminRequest):
        _stub()

    @app.delete(
        "/api/super/admins/{email}",
        response_model=SuperAdminsResponse,
        tags=["super"],
        responses={
            **_ERRORS,
            404: {"model": ErrorResponse, "description": "unknown_admin"},
            422: {"model": ErrorResponse, "description": "cannot_remove_self, set_in_env"},
        },
    )
    async def remove_super_admin(email: str):
        """Remove someone added on this page. Not yourself, and not the .env ones."""
        _stub()

    @app.get("/api/staff/stream", tags=["staff"], responses=_SSE)
    async def staff_stream(clarifications: bool = False):
        """SSE: a snapshot per room on connect, then every change in any room, plus heartbeats.
        With `?clarifications=1` (0.8.0) also a `clarifications` event (the admin list, same body
        as GET /api/staff/clarifications) on connect and after every clarification change.
        A `room_removed` event (`{room_id}`, 0.8.0) follows an Empty of a deleted room."""
        _stub()

    return app


def build_openapi() -> dict[str, Any]:
    app = build_schema_app()
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        separate_input_output_schemas=False,
    )
    components = schema.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    for model in EXTRA_SCHEMA_MODELS:
        extra = model.model_json_schema(ref_template="#/components/schemas/{model}")
        for name, definition in extra.pop("$defs", {}).items():
            schemas.setdefault(name, definition)
        schemas.setdefault(model.__name__, extra)
    components["securitySchemes"] = {
        name: {"type": "apiKey", "in": "cookie", "name": cookie}
        for name, cookie in COOKIE_NAMES.items()
    }
    return schema
