# contracts/

The machine-readable half of the contract. The prose half is [`docs/protocol.md`](../docs/protocol.md).

| Path | What | How it's produced |
|---|---|---|
| `openapi.json` | HTTP API schema and every wire model | Generated: `cd server && uv run python -m scripts.export_openapi`. A test fails if it's stale. Never hand-edit. |
| `timer-fixtures/*.json` | Shared test cases for the timer fold | Hand-written. Python (`server/tests/test_timer_fixtures.py`) and TypeScript (`web/packages/sync-core`, Phase 1+) must both pass every file. |

Changing anything here is a contract change: follow the rules in `docs/protocol.md` §0 (bump the version, add a changelog line).
