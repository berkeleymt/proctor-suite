"""Proctor Suite server. Phase 0: health endpoints only.

Invariant 9: run exactly one process (uvicorn --workers 1).
Invariant 1: /readyz touches Postgres, so it is for ops/monitoring only.
Room devices must never call it.
"""

import asyncio
import os

import asyncpg
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI(title="Proctor Suite", docs_url=None, redoc_url=None)


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
