import { describe, expect, it } from "vitest";
import { bulkSlots, MAIN, plan, rowSlots, STATUSES, WHY, type Status } from "../screens/adminActions";

/**
 * The Timers page's button rules (screens/adminActions.ts). If one of these fails, either the
 * change was a mistake, or the rule really changed: then update the table here AND say so in
 * an ADR (0020 is the current one).
 */

const keys = (st: Status) => rowSlots(st).map((g) => g.map((s) => s.key));
const can = (st: Status) => Object.fromEntries(rowSlots(st).flat().map((s) => [s.key, !s.why]));

describe("room row buttons", () => {
  it("are the same five, in the same groups and order, in every timer state", () => {
    for (const st of STATUSES) expect(keys(st)).toEqual([["main"], ["adjust", "reset"], ["edit", "delete"]]);
  });

  it("keep the same labels in every state, except the main button", () => {
    const rest = (st: Status) => rowSlots(st).flat().slice(1).map((s) => s.label);
    for (const st of STATUSES) expect(rest(st)).toEqual(["+5 min", "Reset", "Edit…", "Delete…"]);
  });

  it("main button is the timer's next step", () => {
    expect(STATUSES.map((st) => [MAIN[st].label, MAIN[st].action])).toEqual([
      ["Allow start", "permit"],
      ["Start", "start"],
      ["Pause", "pause"],
      ["Resume", "resume"],
      ["Time's up", undefined],
    ]);
  });

  it("main button reserves room for its longest label", () => {
    for (const st of STATUSES) expect(rowSlots(st)[0][0].labels).toEqual(STATUSES.map((s) => MAIN[s].label));
  });

  // The server's rules: protocol §5.4 (timer commands), reset only from PAUSED/ENDED, delete
  // refused while a timer is in progress (room_in_progress). 1 = can run, 0 = greyed out.
  it.each<[Status, number[]]>([
    //                main +5  reset edit delete
    ["NOT_PERMITTED", [1, 1, 0, 1, 1]],
    ["PERMITTED", /**/ [1, 1, 0, 1, 1]],
    ["RUNNING", /*  */ [1, 1, 0, 1, 0]],
    ["PAUSED", /*   */ [1, 1, 1, 1, 0]],
    ["ENDED", /*    */ [0, 0, 1, 1, 1]],
  ])("can run only what the server accepts (%s)", (st, want) => {
    const c = can(st);
    expect([c.main, c.adjust, c.reset, c.edit, c.delete].map(Number)).toEqual(want);
  });

  it("say why when greyed out", () => {
    for (const st of STATUSES) for (const s of rowSlots(st).flat()) if (s.why) expect(s.why.length).toBeGreaterThan(10);
    expect(rowSlots("RUNNING")[1][1].why).toBe(WHY.resetRunning);
    expect(rowSlots("NOT_PERMITTED")[1][1].why).toBe(WHY.resetNotStarted);
  });
});

describe("bulk bar buttons", () => {
  const bkeys = (sts: Status[]) => bulkSlots(sts).map((g) => g.map((s) => s.key));

  it("are the same whatever is ticked", () => {
    const want = bkeys([]);
    for (const st of STATUSES) expect(bkeys([st])).toEqual(want);
    expect(bkeys([...STATUSES])).toEqual(want);
  });

  it("use the row's groups: every main action, then +5 min and Reset, then Edit and Delete", () => {
    const [timer, adjust, room] = bulkSlots([]).map((g) => g.map((s) => s.label));
    expect(timer).toEqual(STATUSES.filter((st) => MAIN[st].action).map((st) => MAIN[st].label));
    expect(adjust).toEqual(["+5 min", "Reset"]);
    expect(room).toEqual(["Edit…", "Delete…"]);
  });

  it("agree with the row buttons for a single room", () => {
    for (const st of STATUSES) {
      const bulk = Object.fromEntries(bulkSlots([st]).flat().map((s) => [s.key, !s.why]));
      const row = can(st);
      expect([bulk.adjust, bulk.reset, bulk.edit, bulk.delete]).toEqual([row.adjust, row.reset, row.edit, row.delete]);
      if (MAIN[st].action) expect(bulk[MAIN[st].action!]).toBe(true);
    }
  });

  it("can run if at least one ticked room can", () => {
    const pause = (sts: Status[]) => !bulkSlots(sts)[0][2].why;
    expect(pause(["PAUSED", "ENDED"])).toBe(false);
    expect(pause(["PAUSED", "RUNNING", "ENDED"])).toBe(true);
  });
});

describe("plan (what each action sends)", () => {
  it("starting a room that isn't allowed yet allows it first", () => {
    expect(plan("start", "NOT_PERMITTED")).toEqual(["permit", "start"]);
    expect(plan("start", "PERMITTED")).toEqual(["start"]);
  });

  it("skips rooms in the wrong state", () => {
    expect(plan("start", "RUNNING")).toEqual([]);
    expect(plan("pause", "PAUSED")).toEqual([]);
    expect(plan("adjust", "ENDED")).toEqual([]);
    expect(plan("reset", "RUNNING")).toEqual([]);
  });
});
