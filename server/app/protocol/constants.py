"""Protocol constants (docs/protocol.md §11). Clients and server must agree on these.

Changing any value here is a contract change: bump PROTOCOL_VERSION and add a
changelog line to docs/protocol.md.
"""

PROTOCOL_VERSION = "0.10.0"

# --- Streaming and network behavior (invariant 2) ---
HEARTBEAT_INTERVAL_S = 15  # server sends a heartbeat on every open stream this often
STREAM_DEAD_AFTER_S = 35  # client: nothing heard for this long => stream is dead
REQUEST_TIMEOUT_S = 10  # client: every request has this timeout
BACKOFF_BASE_S = 1  # full-jitter backoff: uniform(0, min(CAP, BASE * 2**attempt))
BACKOFF_CAP_S = 30
SSE_FAILURES_BEFORE_POLLING = 3  # consecutive stream failures before switching to polling
POLL_INTERVAL_S = 5  # polling fallback period...
POLL_JITTER_S = 1  # ...plus a uniform random offset in [-POLL_JITTER_S, +POLL_JITTER_S]

# --- Clock sync (plan §3.5) ---
CLOCK_SAMPLES_KEPT = 8  # keep the lowest-RTT sample out of the last N
CLOCK_RESYNC_INTERVAL_S = 60
CLOCK_JUMP_THRESHOLD_MS = 2000  # wall vs monotonic disagreement that forces a re-sync

# --- Timer ---
TIMER_TICK_MS = 250  # clients recompute remaining(serverNow()) this often
MAX_ADJUST_MS = 10_800_000  # |delta| limit for one ADJUST (3 hours), inclusive

# --- Connectivity banner ---
OFFLINE_RED_AFTER_S = 300  # display turns amber when offline, red after this long

# --- Bounds on list endpoints (invariant 8) ---
MAX_LOGIN_ROOMS = 500
MAX_STAFF_ROOMS = 1000

# --- Auth ---
CLIENT_HEADER = "X-Proctor-Client"  # required (non-empty) on every POST: CSRF guard
SUPER_COOKIE = "super_sid"  # Google-signed-in super-admin page (its own cookie, not a surface)
COOKIE_NAMES = {"display": "display_sid", "control": "control_sid", "staff": "staff_sid"}
STAFF_SESSION_TTL_H = 24

MAX_ROOM_CLARIFICATIONS = 50  # per snapshot (invariant 8)
MAX_ADMIN_CLARIFICATIONS = 200
MAX_CLARIFICATION_EDITS = 10  # earlier wordings kept per clarification (invariant 8)
MAX_BATHROOM_OUT = 50  # students out at once, per room (invariant 8)
MAX_BATHROOM_BACK = 20  # most recent returns sent in a snapshot (invariant 8)
