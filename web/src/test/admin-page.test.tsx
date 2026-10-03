import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { live, moved, ONE_OF_EACH, room, withRooms } from "./admin-harness";
import { WHY } from "../screens/adminActions";
import * as api from "../api";

// The real Timers page, no server: live data comes from the harness, requests are recorded.
vi.mock("../main", () => ({ go: vi.fn() }));
vi.mock("../hooks", async (orig) => ({ ...(await orig<object>()), useLive: (await import("./admin-harness")).useFakeLive, useClock: () => {} }));
vi.mock("../api", async (orig) => ({
  ...(await orig<object>()),
  post: vi.fn(async () => null),
  sendCommand: vi.fn(async (_k: string, s: unknown) => ({ snapshot: s, outcome: "applied" })),
}));

const { Admin } = await import("../screens/Admin");

const ROW = ["+5 min", "Reset", "Edit…", "Delete…"];
const BULK = ["Allow start", "Start", "Pause", "Resume", "+5 min", "Reset", "Edit…", "Delete…"];

const actions = (name: string) => within(screen.getByRole("group", { name: `Actions for ${name}` }));
const names = (q: ReturnType<typeof within>) => q.getAllByRole("button").map((b: HTMLElement) => b.textContent!.trim());
/** The button's visible text only (the main button also holds invisible spacer labels). */
const shownText = (b: HTMLElement) => (b.querySelector(".sized > span:not([aria-hidden])") ?? b).textContent;
const greyed = (b: HTMLElement) => b.getAttribute("aria-disabled") === "true";
const tick = (name: string) => fireEvent.click(screen.getByRole("checkbox", { name: `Select ${name}` }));

beforeEach(() => {
  vi.mocked(api.post).mockClear();
  vi.mocked(api.sendCommand).mockClear();
});

describe("Timers page: room buttons", () => {
  it("every row shows the same buttons in the same order, whatever its state", () => {
    withRooms(ONE_OF_EACH);
    render(<Admin />);
    const want = ["Allow start", "Start", "Pause", "Resume", "Time's up"];
    ONE_OF_EACH.forEach((s, i) => {
      const bs = actions(s.room_name).getAllByRole("button");
      expect(bs.map((b) => b.dataset.slot)).toEqual(["main", "adjust", "reset", "edit", "delete"]);
      expect(shownText(bs[0])).toBe(want[i]);
      expect(bs.slice(1).map((b) => b.textContent)).toEqual(ROW);
    });
  });

  it("main button is named by what it does (not by the hidden spacer labels)", () => {
    withRooms([room("Evans 10", "RUNNING")]);
    render(<Admin />);
    expect(actions("Evans 10").getByRole("button", { name: "Pause" })).toBeTruthy();
  });

  it("Reset is greyed out while running; clicking it says why and sends nothing", () => {
    withRooms([room("Evans 10", "RUNNING")]);
    render(<Admin />);
    const reset = actions("Evans 10").getByRole("button", { name: "Reset" });
    expect(greyed(reset)).toBe(true);
    fireEvent.click(reset);
    expect(screen.getByRole("status").textContent).toBe(WHY.resetRunning);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("Reset on a paused room asks first, then resets", () => {
    withRooms([room("Evans 10", "PAUSED")]);
    render(<Admin />);
    fireEvent.click(actions("Evans 10").getByRole("button", { name: "Reset" }));
    const sheet = within(screen.getByRole("dialog", { name: "Reset Evans 10?" }));
    fireEvent.click(sheet.getByRole("button", { name: "Reset" }));
    expect(api.post).toHaveBeenCalledWith("/api/staff/rooms/evans-10/reset", { session_id: "session-Evans 10" });
  });

  it("Start runs at once; Pause asks first (Shift skips the question)", () => {
    withRooms([room("Evans 10", "PERMITTED"), room("Evans 20", "RUNNING")]);
    render(<Admin />);
    fireEvent.click(actions("Evans 10").getByRole("button", { name: "Start" }));
    expect(vi.mocked(api.sendCommand).mock.calls[0][0]).toBe("start");
    fireEvent.click(actions("Evans 20").getByRole("button", { name: "Pause" }));
    expect(screen.getByRole("dialog", { name: "Pause Evans 20?" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    fireEvent.click(actions("Evans 20").getByRole("button", { name: "Pause" }), { shiftKey: true });
    expect(vi.mocked(api.sendCommand).mock.calls[1][0]).toBe("pause");
  });

  it("a live update changes which buttons can run, not which buttons exist", () => {
    const s = room("Evans 10", "RUNNING");
    withRooms([s]);
    render(<Admin />);
    const before = names(actions("Evans 10"));
    act(() => live.set([moved(s, "PAUSED")]));
    const reset = actions("Evans 10").getByRole("button", { name: "Reset" });
    expect(greyed(reset)).toBe(false);
    expect(names(actions("Evans 10")).slice(1)).toEqual(before.slice(1));
  });
});

describe("Timers page: bulk bar", () => {
  it("only appears while rooms are ticked, and ✕ clears the ticks", () => {
    withRooms(ONE_OF_EACH);
    render(<Admin />);
    expect(screen.queryByRole("toolbar", { name: "Selected rooms" })).toBeNull();
    tick("Evans 10");
    tick("Evans 30");
    const bar = within(screen.getByRole("toolbar", { name: "Selected rooms" }));
    expect(bar.getByText("2 selected")).toBeTruthy();
    fireEvent.click(bar.getByRole("button", { name: "Clear selection" }));
    expect(screen.queryByRole("toolbar", { name: "Selected rooms" })).toBeNull();
  });

  it("shows the same buttons whatever is ticked, greying out what none of them can do", () => {
    withRooms(ONE_OF_EACH);
    render(<Admin />);
    tick("Evans 30"); // running
    const bar = () => within(screen.getByRole("group", { name: "Actions for selected rooms" }));
    expect(names(bar())).toEqual(BULK);
    const state = () => Object.fromEntries(bar().getAllByRole("button").map((b) => [b.textContent, !greyed(b)]));
    expect(state()).toMatchObject({ Pause: true, Resume: false, Reset: false, "Delete…": false });
    tick("Evans 40"); // + paused
    expect(names(bar())).toEqual(BULK);
    expect(state()).toMatchObject({ Pause: true, Resume: true, Reset: true, "Delete…": false });
  });

  it("asks before acting, says how many rooms, and skips the rest", () => {
    withRooms(ONE_OF_EACH);
    render(<Admin />);
    tick("Evans 30");
    tick("Evans 40");
    fireEvent.click(screen.getByRole("toolbar").querySelector<HTMLElement>('[data-slot="pause"]')!);
    const sheet = screen.getByRole("dialog", { name: "Pause 1 room?" });
    expect(sheet.textContent).toMatch(/1 selected room is skipped/);
  });
});
