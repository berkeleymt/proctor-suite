import type { Snapshot } from "../api";

/**
 * Which timer buttons the Timers page shows, and when each one can run. The room rows, the bulk
 * bar and the tests all read from here, so there is one copy of the rules. They mirror the
 * server: protocol §5.4 (timer commands) and the reset endpoint (only paused or finished rooms).
 */

export type Status = Snapshot["timer"]["status"];
/** One request to the server: a timer command, or the reset endpoint. */
export type Kind = "permit" | "start" | "pause" | "resume" | "adjust" | "reset";
/** What an admin asks for. "start" on a room that isn't allowed yet sends permit, then start. */
export type Action = Kind;
export type Slot = "main" | "adjust" | "reset" | "edit" | "delete";
/** A button's content before it's wired up: `why` is "" when it can run. */
export type SlotSpec = { key: string; label: string; labels?: readonly string[]; tone?: "primary" | "danger"; action?: Action; why: string };

export const STATUSES = ["NOT_PERMITTED", "PERMITTED", "RUNNING", "PAUSED", "ENDED"] as const satisfies readonly Status[];

/** The requests one action sends to a room in this state, in order. None = the room is skipped. */
export function plan(action: Action, st: Status): Kind[] {
  if (action === "adjust") return st === "ENDED" ? [] : ["adjust"];
  if (action === "pause") return st === "RUNNING" ? ["pause"] : [];
  if (action === "resume") return st === "PAUSED" ? ["resume"] : [];
  if (action === "reset") return st === "PAUSED" || st === "ENDED" ? ["reset"] : [];
  if (action === "permit") return st === "NOT_PERMITTED" ? ["permit"] : [];
  return st === "NOT_PERMITTED" ? ["permit", "start"] : st === "PERMITTED" ? ["start"] : [];
}

/** Deleting signs everyone out, so it waits until no timer is in progress (server: room_in_progress). */
export const canDelete = (st: Status) => st !== "RUNNING" && st !== "PAUSED";

/** A row's main button is the timer's next step. */
export const MAIN: Record<Status, { label: string; action?: Action; tone?: "primary" }> = {
  NOT_PERMITTED: { label: "Allow start", action: "permit" },
  PERMITTED: { label: "Start", action: "start", tone: "primary" },
  RUNNING: { label: "Pause", action: "pause" },
  PAUSED: { label: "Resume", action: "resume", tone: "primary" },
  ENDED: { label: "Time's up" },
};
export const MAIN_LABELS = STATUSES.map((st) => MAIN[st].label);

export const WHY = {
  timeUp: "Time is up. Reset the room to run it again.",
  resetNotStarted: "Nothing to reset yet. The timer hasn't started.",
  resetRunning: "Pause first. Only paused or finished rooms can be reset.",
  deleteBusy: "A timer is in progress here. Finish or reset it first.",
  noneSelected: "None of the selected rooms can do that right now.",
} as const;

const resetWhy = (st: Status) => (plan("reset", st).length ? "" : st === "RUNNING" ? WHY.resetRunning : WHY.resetNotStarted);

/** One room's buttons: always the same five, in the same places. Groups: timer, then the room itself. */
export function rowSlots(st: Status): SlotSpec[][] {
  const m = MAIN[st];
  return [
    [{ key: "main", label: m.label, labels: MAIN_LABELS, tone: m.tone, action: m.action, why: m.action ? "" : WHY.timeUp }],
    [
      { key: "adjust", label: "+5 min", action: "adjust", why: plan("adjust", st).length ? "" : WHY.timeUp },
      { key: "reset", label: "Reset", action: "reset", why: resetWhy(st) },
    ],
    [
      { key: "edit", label: "Edit…", why: "" },
      { key: "delete", label: "Delete…", tone: "danger", why: canDelete(st) ? "" : WHY.deleteBusy },
    ],
  ];
}

/** The bulk bar: one button per action, in the row's order. A button can run if any selected room can. */
export function bulkSlots(sts: Status[]): SlotSpec[][] {
  const any = (a: Action) => (sts.some((st) => plan(a, st).length) ? "" : WHY.noneSelected);
  return [
    [
      { key: "permit", label: "Allow start", action: "permit", why: any("permit") },
      { key: "start", label: "Start", tone: "primary", action: "start", why: any("start") },
      { key: "pause", label: "Pause", action: "pause", why: any("pause") },
      { key: "resume", label: "Resume", tone: "primary", action: "resume", why: any("resume") },
    ],
    [
      { key: "adjust", label: "+5 min", action: "adjust", why: any("adjust") },
      { key: "reset", label: "Reset", action: "reset", why: any("reset") },
    ],
    [
      { key: "edit", label: "Edit…", why: "" },
      { key: "delete", label: "Delete…", tone: "danger", why: sts.some(canDelete) ? "" : WHY.deleteBusy },
    ],
  ];
}
