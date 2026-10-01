"""Proctor Suite server. Slice 1: health + in-memory auth/time/commands (app/api.py).

Invariant 9: run exactly one process (uvicorn --workers 1).
Invariant 1: /readyz touches Postgres, so it is for ops/monitoring only.
Room devices must never call it.
"""

import asyncio
import os
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app import db
from app.api import router, store


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Load state from Postgres before serving. If the database is down, fail to start loudly."""
    url = os.environ.get("DATABASE_URL")
    pool = None
    if url:
        pool = await db.connect(url)
        await store.load(pool)
    yield
    if pool:
        await pool.close()


app = FastAPI(title="Proctor Suite", docs_url=None, redoc_url=None, lifespan=lifespan)


@app.exception_handler(asyncpg.PostgresError)
@app.exception_handler(OSError)
@app.exception_handler(TimeoutError)
async def db_down(_: Request, __: Exception) -> JSONResponse:
    """A failed commit changed nothing (invariant 5). Clients retry with the same command_id."""
    detail = {"error": "unavailable", "message": "Server couldn't save that. Try again."}
    return JSONResponse({"detail": detail}, status_code=503)


app.include_router(router)


@app.get("/healthz", response_class=PlainTextResponse)
async def healthz() -> str:
    """Liveness: the process is up. Never touches the database."""
    return "ok"


@app.get("/readyz", response_class=PlainTextResponse)
async def readyz() -> PlainTextResponse:
    """Readiness: Postgres is reachable. Used by ops, not by room devices."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        return PlainTextResponse("DATABASE_URL not set", status_code=503)
    try:
        conn = await asyncpg.connect(url, timeout=2)
        try:
            await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=2)
        finally:
            await conn.close()
    except Exception as exc:  # noqa: BLE001 - report any failure as not ready
        return PlainTextResponse(f"not ready: {type(exc).__name__}", status_code=503)
    return PlainTextResponse("ready")
