# Status tracking (read this first, every session)

Humans and agents use this folder to know where the project is and to leave notes for the next person or agent.

## Files

| File | Purpose | Who edits |
|---|---|---|
| `STATUS.md` | One-page dashboard: current phase, gate state, blockers, next actions | Anyone, but keep it short and true |
| `phase-N.md` | Checklist for each phase, copied from `development-plan.md` §6, with evidence per item | Owner of the item |
| `log/YYYY-MM-DD-<who>-<topic>.md` | One note per working session (see `log/_TEMPLATE.md`) | The agent or human who did the work |

## Rules

1. **Start of session:** read `STATUS.md`, the current `phase-N.md`, and the last few files in `log/`.
2. **End of session:** add one file to `log/`, and tick or untick items in `phase-N.md`. Update `STATUS.md` if the gate state or blockers changed.
3. **A box is ticked only with evidence**: a commit hash, a PR number, a URL that returned the expected result, a CI run, or a message from the named approver. No evidence, no tick.
4. Mark things you could not verify as `[?]` (unverified) rather than `[x]`. Never guess.
5. Only humans can tick approvals ("Ian approved", "Forrest approved"). Agents may record that an approval is *requested*.
6. `docs/protocol.md` and `contracts/` still need both Ian and Forrest, as in `CLAUDE.md`.
7. Don't rewrite old log files. Add a new one that corrects them.

## Legend

`[x]` done, with evidence · `[ ]` not done · `[?]` probably done, not verified · `[~]` partly done · `[-]` dropped or deferred (say why)
