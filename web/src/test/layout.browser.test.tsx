import { describe, expect, it, vi } from "vitest";
import { page } from "@vitest/browser/context";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { live, moved, ONE_OF_EACH, withRooms } from "./admin-harness";
import { STATUSES } from "../screens/adminActions";
import "../styles.css";

/**
 * Layout in a real browser (headless Chromium): things jsdom can't measure. Positions are compared
 * with each other, never with saved pixels, so font differences between machines don't matter.
 * These pin the Timers page rule "buttons never move or resize" (ADR 0020).
 */

vi.mock("../main", () => ({ go: vi.fn() }));
vi.mock("../hooks", async (orig) => ({ ...(await orig<object>()), useLive: (await import("./admin-harness")).useFakeLive, useClock: () => {} }));
vi.mock("../api", async (orig) => ({ ...(await orig<object>()), post: vi.fn(async () => null), sendCommand: vi.fn() }));

const { Admin } = await import("../screens/Admin");

type Box = { x: number; y: number; w: number; h: number };
const box = (el: Element): Box => {
  const r = el.getBoundingClientRect();
  return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
};
const rowGroup = (name: string) => screen.getByRole("group", { name: `Actions for ${name}` });
const slots = (group: Element) => [...group.querySelectorAll<HTMLElement>("button")];
/** Every action button on the page, with where it is: the whole table's button layout at once. */
const allButtons = () => Object.fromEntries(ONE_OF_EACH.flatMap((s) => slots(rowGroup(s.room_name)).map((b) => [`${s.room_name} ${b.dataset.slot}`, { ...box(b) }])));
const tableBox = () => box(document.querySelector(".table")!);

function show(rooms = ONE_OF_EACH) {
  withRooms(rooms);
  render(<Admin />);
}

describe("Timers page layout", () => {
  it("each button sits at the same x and width in every row, whatever the row's state", () => {
    show();
    const rows = ONE_OF_EACH.map((s) => slots(rowGroup(s.room_name)).map((b) => ({ x: box(b).x, w: box(b).w })));
    for (const r of rows) expect(r).toEqual(rows[0]);
  });

  it("a room going through every state moves no button anywhere on the page", () => {
    show();
    const before = allButtons();
    const table = tableBox();
    for (const st of STATUSES) {
      act(() => live.set([moved(ONE_OF_EACH[0], st), ...ONE_OF_EACH.slice(1)]));
      expect(allButtons()).toEqual(before);
      expect(tableBox()).toEqual(table);
    }
  });

  it("all rooms changing state together moves nothing (no column resizes)", () => {
    show();
    const before = allButtons();
    for (const st of STATUSES) {
      act(() => live.set(ONE_OF_EACH.map((s) => moved(s, st))));
      expect(allButtons()).toEqual(before);
    }
  });

  it("ticking rooms floats the bulk bar over the table without moving it", () => {
    show();
    const table = tableBox();
    const buttons = allButtons();
    fireEvent.click(screen.getByRole("checkbox", { name: "Select Evans 30" }));
    const bar = screen.getByRole("toolbar", { name: "Selected rooms" });
    expect(getComputedStyle(bar).position).toBe("fixed");
    expect(box(bar).y).toBeLessThan(table.y + table.h); // over the table, not above it
    expect(tableBox()).toEqual(table);
    expect(allButtons()).toEqual(buttons);
  });

  it("the bulk bar's buttons keep their size and place as more rooms are ticked", () => {
    show();
    fireEvent.click(screen.getByRole("checkbox", { name: "Select Evans 10" }));
    const bar = () => screen.getByRole("toolbar", { name: "Selected rooms" });
    const layout = () => ({ bar: box(bar()), buttons: slots(bar()).map(box) });
    const first = layout();
    for (const s of ONE_OF_EACH.slice(1)) {
      fireEvent.click(screen.getByRole("checkbox", { name: `Select ${s.room_name}` }));
      expect(layout()).toEqual(first);
    }
  });

  it("rows and the bulk bar use the same button size", () => {
    show();
    fireEvent.click(screen.getByRole("checkbox", { name: "Select Evans 10" }));
    const heights = new Set([...document.querySelectorAll(".acts .act")].map((b) => box(b).h));
    expect(heights.size).toBe(1);
  });

  it("the why-not note floats too: clicking a greyed-out button moves nothing", () => {
    show();
    const table = tableBox();
    fireEvent.click(slots(rowGroup("Evans 30")).find((b) => b.dataset.slot === "reset")!);
    expect(screen.getByRole("status").hidden).toBe(false);
    expect(getComputedStyle(screen.getByRole("status")).position).toBe("fixed");
    expect(tableBox()).toEqual(table);
  });

  it.each([1280, 1024, 768])("buttons never wrap to a second line at %ipx wide", async (width) => {
    await page.viewport(width, 800);
    show();
    for (const s of ONE_OF_EACH) {
      const ys = new Set(slots(rowGroup(s.room_name)).map((b) => box(b).y));
      expect(ys.size).toBe(1);
    }
    await page.viewport(1280, 800);
  });
});
