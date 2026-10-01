"""Builds the OpenAPI document for the contract (contracts/openapi.json).

This is a SCHEMA-ONLY app: the route functions are stubs and are never mounted in the real
server (app.main). When the real routers exist, the export script should switch to building
from them (and this file goes away); the contract test will fail if the two ever disagree.
"""

from typing import Annotated, Any

from fastapi import FastAPI, Path, Query, Response
from fastapi.openapi.utils import get_openapi

from app.protocol.constants import COOKIE_NAMES, PROTOCOL_VERSION
from app.protocol.models import (
    EXTRA_SCHEMA_MODELS,
    Command,
    CommandResponse,
    CreateRoomRequest,
    ErrorResponse,
    Identity,
    LoginOptionsResponse,
    RoomIdentity,
    RoomLoginRequest,
    RoomSnapshot,
    StaffIdentity,
    StaffLoginRequest,
    StaffRoomsResponse,
    Surface,
    TimeResponse,
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
        "description": "text/event-stream. Frames are SnapshotMessage and HeartbeatMessage.",
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
    async def room_stream(room_id: Annotated[str, Path()]):
        """SSE: current snapshot immediately, then every change, plus heartbeats."""
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

    @app.get("/api/staff/stream", tags=["staff"], responses=_SSE)
    async def staff_stream():
        """SSE: a snapshot per room on connect, then every change in any room, plus heartbeats."""
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
