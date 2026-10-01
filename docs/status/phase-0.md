# Phase 0: Foundations

Source: `development-plan.md` §6 (deliverables and gate), §5 (AWS), §7.4 (contract sprint).
**Planned window:** Sep 26 – Sep 29, 2026. **Last updated:** 2026-10-01.

**Verdict: complete, pending a final commit/push of the contract files and a green CI run on them.** AWS and CI were reported working by the PM on 2026-10-01; the contract sprint was done on 2026-10-01 (see `log/2026-10-01-claude-contract-sprint.md`).

## A. AWS account and prod server live with HTTPS (owner: Forrest)

- [x] AWS prod server live, `/healthz` returns `ok` over HTTPS. *Reported working by the PM, 2026-10-01. No URL recorded: add it here when convenient.*
- [?] Account hygiene items from plan §5 steps 1–3 (shared BMT email, root MFA, budget alert, IAM role). Not gate items; not verified.
- [ ] Not Phase 0 gate items, listed so they aren't forgotten:
  - [ ] S3 bucket + lifecycle rule + EBS snapshot policy (Step 9)
  - [ ] CloudWatch recover alarm + UptimeRobot (Step 10)
  - [ ] `proctor-staging` built and stopped

## B. Repo skeleton, CI, deploy scripts

- [x] Server skeleton: FastAPI `/healthz` and `/readyz`, single worker. *Commit `69ebf03`.*
- [x] `server/Dockerfile` pinned, `--workers 1` (invariant 9).
- [x] `infra/` compose, Caddyfile, `.env.example`, `bootstrap.sh`, `deploy.sh` (+ `--rollback`, `--restart`), `lib.sh`.
- [x] `.gitattributes` forces LF on `*.sh`.
- [x] CI is green. *Reported by the PM, 2026-10-01, for the commits up to `b383d65`. **Re-check after the contract files are pushed.***
- [ ] `infra/README.md` with the click-by-click AWS steps. Deferred; not a gate item.
- [-] Alembic and the `deploy.sh` migration step: placeholder only. Needed before the first schema (Phase 1/2).
- [-] CI jobs for later phases (Vitest, fixtures in both languages, OpenAPI→TS types check, Playwright). Added when `web/` exists.

## C. Contract sprint

- [x] D1–D12 approved. *By the PM, 2026-10-01. Ian's own agreement is not separately recorded.*
- [x] Open questions resolved (2026-10-01): proctors cannot end early; staff can start on behalf; login is the room-name dropdown. Recorded in `docs/adr/0001`, `0002`.
- [x] `docs/protocol.md` v0.1.0 written.
- [x] Pydantic wire models + constants: `server/app/protocol/`.
- [x] OpenAPI exported to `contracts/openapi.json`; a test fails if it is stale.
- [-] Generated TypeScript types: deferred to the first frontend ticket (`web/` doesn't exist yet). Input is ready: `contracts/openapi.json`.
- [x] 23 timer fixtures in `contracts/timer-fixtures/` (plan asked for 20), plus a reference Python fold (`server/app/fold.py`) that passes all of them. Mutation-checked: breaking a fixture value or the sort order makes tests fail.
- [x] `CLAUDE.md` with the invariants (and now the protocol/contract rules).
- [x] ADRs for today's decisions (`docs/adr/0001`–`0003`).
- [-] ADRs for D1–D4/D7 (single process, SSE, event-list timer, EC2+Compose): optional, still unwritten.
- [-] `server/CLAUDE.md`: deferred.
- [-] CODEOWNERS and branch protection: **dropped** by PM decision (ADR 0003).
- [x] "Both devs have approved the contract": **waived by the PM** (ADR 0003). Not an approval by Ian/Forrest.

## D. Gate

- [x] `healthz` is green on AWS (reported by PM)
- [x] CI is green (reported by PM; re-check on the contract commit)
- [x] Contract approved (waived by PM, ADR 0003)

## Follow-ups before Phase 1 work starts
1. Push the contract files; confirm CI stays green (it now runs 67 server tests including the fixtures).
2. Resolve protocol §13 open questions when convenient (none block Phase 1).
