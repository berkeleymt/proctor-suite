# 0003: No developer approval gate on contract changes

**Date:** 2026-10-01 · **Decided by:** PM · **Supersedes:** development-plan.md §7.3 rule 3 and §6 Phase 0 gate wording ("both devs have approved the contract")

## Context
The plan required both Ian and Forrest to approve every change to `contracts/` and `docs/protocol.md` (CODEOWNERS + branch protection). The PM decided the team will commit directly to GitHub without approvals.

## Decision
No CODEOWNERS file and no branch-protection requirement for the contract. To keep two people's agents from drifting apart, every contract change must still:
1. bump `PROTOCOL_VERSION` in `server/app/protocol/constants.py`,
2. add a line to the changelog in `docs/protocol.md` §14,
3. re-export `contracts/openapi.json` (a test fails if it is stale) and keep the timer fixtures passing,
4. say in the PR/commit message that it touches the contract.

## Consequences
- The Phase 0 gate item "both devs approved the contract" is recorded as **waived by the PM**, not as an approval by Ian and Forrest.
- Risk: a contract change can land without the other developer noticing. The version bump and changelog are the mitigation; revisit if it causes a problem.
