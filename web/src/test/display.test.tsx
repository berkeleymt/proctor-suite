import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Snapshot } from "../api";
import { CLAR_STEPS, effective, readLocal, TIMER_PCT_DEFAULT, TIMER_PCTS, type Local } from "../displaySettings";
import { STEPS_VH } from "../components/ClarList";

vi.mock("../main", () => ({ go: vi.fn() })); // main.tsx mounts the whole app on import

const { View, CLARS_HIDDEN } = await import("../screens/Display");
const { DisplaySizes } = await import("../screens/Proctor");
const { finishedNote } = await import("../screens/Clarifications");

type Status = Snapshot["timer"]["status"];
const ROOM = "evans-10";
const KEY = `display:${ROOM}`;

function snap(status: Status, over: Partial<Snapshot> = {}, display: Partial<Snapshot["display"]> = {}): Snapshot {
  return {
    room_id: ROOM,
    room_name: "Evans 10",
    test_name: "Individual Round",
    session_id: "evans-10-1",
    version: 10,
    server_time_ms: Date.now(),
    timer: { status, duration_ms: 3_600_000, adjust_total_ms: 0, elapsed_banked_ms: 0, running_since_ms: status === "RUNNING" ? Date.now() : null },
    deleted: false,
    doc_url: null,
    clarifications: [{ id: "c1", body: "Problem 3: assume x is positive.", created_at_ms: 1, previous: [], edited_at_ms: null }],
    students_out: 0,
    bathroom_out: [],
    bathroom_back: [],
    display: { timer_zoom_pct: 80, clar_size: "auto", timer_zoom_at_ms: null, clar_size_at_ms: null, ...display },
    ...over,
  } as Snapshot;
}

/** Another window of this browser saved something (this window hears a `storage` event). */
function fromOtherWindow(key: string, value: string) {
  localStorage.setItem(key, value);
  act(() => {
    window.dispatchEvent(new StorageEvent("storage", { key, newValue: value }));
  });
}

const clarList = (c: HTMLElement) => c.querySelector(".clars") as HTMLElement;

// ---------------------------------------------------------------- the contract

describe("sizes match the server contract", () => {
  const repo = resolve(process.cwd(), ".."); // tests run from web/
  const api = JSON.parse(readFileSync(resolve(repo, "contracts/openapi.json"), "utf8"));
  const consts = readFileSync(resolve(repo, "server/app/protocol/constants.py"), "utf8");
  const props = api.components.schemas.SetDisplayRequest.properties;

  it("timer steps and default", () => {
    const allowed = props.timer_zoom_pct.anyOf.find((x: { enum?: number[] }) => x.enum).enum;
    expect(TIMER_PCTS).toEqual([...allowed].sort((a, b) => a - b));
    expect(consts).toMatch(new RegExp(`^DISPLAY_TIMER_ZOOM_DEFAULT = ${TIMER_PCT_DEFAULT}\\b`, "m"));
  });

  it("clarification steps", () => {
    const int = props.clar_size.anyOf.find((x: { type?: string }) => x.type === "integer");
    expect(int.maximum + 1).toBe(CLAR_STEPS);
    expect(STEPS_VH).toHaveLength(CLAR_STEPS);
  });
});

// ---------------------------------------------------------------- the merge rule

describe("what the projector shows", () => {
  const pend = (value: unknown, at: number, ack?: number) => ({ value, at, id: "x", ...(ack === undefined ? {} : { ack }) });

  it("is the server's value when this browser saved nothing", () => {
    expect(effective(snap("RUNNING", {}, { timer_zoom_pct: 60, clar_size: 3 }), {})).toEqual({ timer_zoom_pct: 60, clar_size: 3 });
  });

  it("is an unsent click only if it is newer than the server's", () => {
    const s = snap("RUNNING", {}, { timer_zoom_pct: 60, timer_zoom_at_ms: 1000 });
    expect(effective(s, { timer_zoom_pct: pend(90, 2000) } as Local).timer_zoom_pct).toBe(90);
    expect(effective(s, { timer_zoom_pct: pend(90, 500) } as Local).timer_zoom_pct).toBe(60); // another proctor clicked later
    expect(effective(s, { timer_zoom_pct: pend(90, 1000) } as Local).timer_zoom_pct).toBe(60); // tie: the server's
    expect(effective(snap("RUNNING"), { clar_size: pend(5, 1) } as Local).clar_size).toBe(5); // server never set
  });

  it("is a sent click until this page has the room version that includes it", () => {
    const s = snap("RUNNING", { version: 10 }, { timer_zoom_pct: 60, timer_zoom_at_ms: 9_999_999 });
    expect(effective(s, { timer_zoom_pct: pend(90, 1, 11) } as Local).timer_zoom_pct).toBe(90);
    expect(effective(s, { timer_zoom_pct: pend(90, 1, 10) } as Local).timer_zoom_pct).toBe(60);
  });

  it("handles each field on its own", () => {
    const s = snap("RUNNING", {}, { timer_zoom_pct: 60, timer_zoom_at_ms: 5000, clar_size: 1, clar_size_at_ms: 5000 });
    expect(effective(s, { timer_zoom_pct: pend(100, 6000), clar_size: pend(7, 4000) } as Local)).toEqual({ timer_zoom_pct: 100, clar_size: 1 });
  });

  it("ignores junk saved in the browser", () => {
    for (const junk of ["not json", "[]", "null", '{"timer_zoom_pct": {"value": 85, "at": 1, "id": "a"}}', '{"clar_size": {"value": 8, "at": 1, "id": "a"}}', '{"clar_size": {"value": 2, "id": "a"}}', '{"clar_size": {"value": 2, "at": 1}}']) {
      localStorage.setItem(KEY, junk);
      expect(readLocal(ROOM)).toEqual({});
    }
    localStorage.setItem(KEY, '{"clar_size": {"value": "auto", "at": 5, "id": "a", "ack": 3}, "extra": 1}');
    expect(readLocal(ROOM)).toEqual({ clar_size: { value: "auto", at: 5, id: "a", ack: 3 } });
  });
});

// ---------------------------------------------------------------- the projector

describe("projector display", () => {
  it.each<Status>(["NOT_PERMITTED", "PERMITTED", "RUNNING", "PAUSED", "ENDED"])("has no controls (%s)", (status) => {
    render(<View s={snap(status)} online />);
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(screen.queryAllByRole("group")).toHaveLength(0);
  });

  it.each<Status>(["NOT_PERMITTED", "PERMITTED", "RUNNING", "PAUSED"])("shows clarifications until time is up (%s)", (status) => {
    render(<View s={snap(status)} online />);
    expect(screen.getByText("Clarifications")).toBeTruthy();
    expect(screen.getByText(/Problem 3: assume x is positive/)).toBeTruthy();
    expect(screen.queryByText(new RegExp(CLARS_HIDDEN))).toBeNull();
  });

  it("says clarifications are hidden once time is up", () => {
    render(<View s={snap("ENDED")} online />);
    expect(screen.queryByText(/Problem 3/)).toBeNull();
    expect(screen.getByText(new RegExp(CLARS_HIDDEN))).toBeTruthy();
  });

  it("says nothing about clarifications at the end if there were none", () => {
    render(<View s={snap("ENDED", { clarifications: [] })} online />);
    expect(screen.queryByText(new RegExp(CLARS_HIDDEN))).toBeNull();
  });

  it("uses the room's clarification size from the server", () => {
    const { container, rerender } = render(<View s={snap("RUNNING")} online />);
    expect(clarList(container).classList.contains("manual")).toBe(false); // Auto
    rerender(<View s={snap("RUNNING", { version: 11 }, { clar_size: 4, clar_size_at_ms: 1 })} online />);
    expect(clarList(container).style.fontSize).toBe("8vh");
  });

  it("follows an unsent click from the proctor page in this browser at once", () => {
    const { container } = render(<View s={snap("RUNNING")} online />);
    fromOtherWindow(KEY, JSON.stringify({ clar_size: { value: 1, at: Date.now(), id: "p1" } }));
    expect(clarList(container).style.fontSize).toBe("3.5vh");
  });
});

// ---------------------------------------------------------------- the proctor page

type Call = { url: string; body: Record<string, unknown> };

/** A fake server: records PATCH bodies; `reply` decides each answer. */
function fakeServer(reply: (call: Call, n: number) => Response | Promise<Response> | "offline") {
  const calls: Call[] = [];
  let inFlight = 0;
  let maxInFlight = 0;
  let answered = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit) => {
      const call = { url, body: JSON.parse(String(init.body)) };
      calls.push(call);
      inFlight++;
      maxInFlight = Math.max(maxInFlight, inFlight);
      try {
        await new Promise((ok) => setTimeout(ok, 5));
        const r = await reply(call, calls.length);
        if (r === "offline") throw new TypeError("Failed to fetch");
        return r;
      } finally {
        inFlight--;
        answered++;
      }
    }),
  );
  return { calls, maxInFlight: () => maxInFlight, answered: () => answered };
}

const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });

/** The server applying a click: returns the room with it and a new version. */
const applied = (call: Call, version: number) => {
  const { timer_zoom_pct, clar_size, claimed_at_ms } = call.body as { timer_zoom_pct?: 40; clar_size?: number; claimed_at_ms: number };
  return json(
    snap("RUNNING", { version }, {
      ...(timer_zoom_pct ? { timer_zoom_pct, timer_zoom_at_ms: claimed_at_ms } : {}),
      ...(clar_size !== undefined ? { clar_size, clar_size_at_ms: claimed_at_ms } : {}),
    }),
  );
};

/** The proctor page's state handling, as in Panel: snapshots from responses land in `data`. */
function Panel({ initial }: { initial: Snapshot }) {
  const [s, setS] = useState<Snapshot | null>(initial);
  return (
    s && (
      <>
        <span data-testid="version">{s.version}</span>
        <DisplaySizes s={s} setData={setS} />
      </>
    )
  );
}

const readout = (name: string) => screen.getByLabelText(name).textContent;

describe("proctor page: projector sizes", () => {
  beforeEach(() => vi.spyOn(Math, "random").mockReturnValue(0)); // backoff waits 0 ms
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("has timer and clarification size controls with a readout", () => {
    fakeServer(() => "offline");
    render(<Panel initial={snap("RUNNING", {}, { timer_zoom_pct: 60, clar_size: 2 })} />);
    expect(screen.getByRole("group", { name: "Display timer size" })).toBeTruthy();
    expect(screen.getByRole("group", { name: "Clarification size" })).toBeTruthy();
    expect(readout("Display timer size now")).toBe("60%");
    expect(readout("Clarification size now")).toBe("3 of 8");
  });

  it("sends a click to the server, which then holds it", async () => {
    const srv = fakeServer((c) => applied(c, 11));
    render(<Panel initial={snap("RUNNING")} />);
    fireEvent.click(screen.getByLabelText("Display timer size: bigger"));
    expect(readout("Display timer size now")).toBe("90%"); // at once, before the server answers
    expect(readLocal(ROOM).timer_zoom_pct).toMatchObject({ value: 90 });
    await waitFor(() => expect(screen.getByTestId("version").textContent).toBe("11"));
    expect(srv.calls).toHaveLength(1);
    expect(srv.calls[0].url).toBe(`/api/rooms/${ROOM}/display`);
    const body = srv.calls[0].body;
    expect(Object.keys(body).sort()).toEqual(["claimed_at_ms", "command_id", "timer_zoom_pct"]);
    expect(body.timer_zoom_pct).toBe(90);
    expect(body.command_id).toBe(readLocal(ROOM).timer_zoom_pct!.id);
    await waitFor(() => expect(readLocal(ROOM).timer_zoom_pct!.ack).toBe(11));
    expect(readout("Display timer size now")).toBe("90%");
  });

  it("keeps trying while offline, one request at a time, with the same command id", async () => {
    const srv = fakeServer((c, n) => (n < 3 ? "offline" : applied(c, 12)));
    render(<Panel initial={snap("RUNNING")} />);
    fireEvent.click(screen.getByLabelText("Clarifications: bigger"));
    await waitFor(() => expect(screen.getByText(/Not saved yet/)).toBeTruthy());
    await waitFor(() => expect(screen.getByTestId("version").textContent).toBe("12"));
    expect(srv.calls).toHaveLength(3);
    expect(new Set(srv.calls.map((c) => c.body.command_id)).size).toBe(1); // a retry, not a new click
    expect(srv.maxInFlight()).toBe(1);
    await waitFor(() => expect(screen.queryByText(/Not saved yet/)).toBeNull());
  });

  it("sends only the latest of several quick clicks once the first is answered", async () => {
    const srv = fakeServer((c, n) => applied(c, 10 + n));
    render(<Panel initial={snap("RUNNING")} />);
    fireEvent.click(screen.getByLabelText("Display timer size: bigger")); // 90
    fireEvent.click(screen.getByLabelText("Display timer size: bigger")); // 100
    fireEvent.click(screen.getByLabelText("Display timer size: smaller")); // 90
    fireEvent.click(screen.getByLabelText("Display timer size: smaller")); // 80
    await waitFor(() => expect(readLocal(ROOM).timer_zoom_pct?.ack).toBeDefined());
    expect(srv.maxInFlight()).toBe(1);
    expect(srv.calls.at(-1)!.body.timer_zoom_pct).toBe(80);
    expect(srv.calls.length).toBeLessThanOrEqual(2); // the first click, then the newest
    expect(readout("Display timer size now")).toBe("80%");
  });

  it("drops a click the server refuses and says so", async () => {
    fakeServer(() => json({ detail: { error: "forbidden", message: "Only this room's proctor can do that." } }, 403));
    render(<Panel initial={snap("RUNNING", {}, { clar_size: 4 })} />);
    fireEvent.click(screen.getByRole("button", { name: "Auto" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/Only this room's proctor/));
    expect(readLocal(ROOM).clar_size).toBeUndefined();
    expect(readout("Clarification size now")).toBe("5 of 8"); // back to the room's value
  });

  it("keeps a click while signed out (a server restart) and sends it once signed back in", async () => {
    let signedIn = false;
    const srv = fakeServer((c) => (signedIn ? applied(c, 13) : json({ detail: { error: "unauthenticated", message: "Not logged in." } }, 401)));
    const { unmount } = render(<Panel initial={snap("RUNNING")} />);
    fireEvent.click(screen.getByLabelText("Display timer size: smaller"));
    await waitFor(() => expect(srv.answered()).toBeGreaterThan(0)); // the 401 came back...
    await waitFor(() => expect(screen.getByText(/Not saved yet/)).toBeTruthy()); // ...and was handled
    unmount(); // the page goes to the login screen
    expect(readLocal(ROOM).timer_zoom_pct).toMatchObject({ value: 70 });
    expect(readLocal(ROOM).timer_zoom_pct!.ack).toBeUndefined();
    signedIn = true;
    render(<Panel initial={snap("RUNNING")} />); // back on the proctor page
    expect(readout("Display timer size now")).toBe("70%");
    await waitFor(() => expect(readLocal(ROOM).timer_zoom_pct!.ack).toBe(13));
    expect(new Set(srv.calls.map((c) => c.body.command_id)).size).toBe(1);
  });

  it("shows another proctor's change (the server's value) over an older saved click", () => {
    fakeServer(() => "offline");
    localStorage.setItem(KEY, JSON.stringify({ timer_zoom_pct: { value: 40, at: 1000, id: "old", ack: 3 } }));
    render(<Panel initial={snap("RUNNING", { version: 10 }, { timer_zoom_pct: 70, timer_zoom_at_ms: 5000 })} />);
    expect(readout("Display timer size now")).toBe("70%");
  });

  it("steps clarification size from what Auto showed on this browser's projector", () => {
    fakeServer(() => "offline");
    localStorage.setItem("clarsize:auto", "3"); // written by the display window
    render(<Panel initial={snap("RUNNING")} />);
    expect(readout("Clarification size now")).toBe("4 of 8");
    fireEvent.click(screen.getByLabelText("Clarifications: bigger"));
    expect(readLocal(ROOM).clar_size).toMatchObject({ value: 4 });
    expect(readout("Clarification size now")).toBe("5 of 8");
  });

  it("tells the proctor when clarifications are hidden, and counts them otherwise", () => {
    fakeServer(() => "offline");
    const { unmount } = render(<Panel initial={snap("ENDED")} />);
    expect(screen.getByText(CLARS_HIDDEN)).toBeTruthy();
    unmount();
    render(<Panel initial={snap("NOT_PERMITTED")} />);
    expect(screen.getByText("1 clarification on the display.")).toBeTruthy();
  });
});

describe("admin: posting to finished rooms", () => {
  it("explains why finished rooms won't show it", () => {
    expect(finishedNote(1, 1)).toMatch(/^This room has finished\. .*until the timer is reset\.$/);
    expect(finishedNote(3, 3)).toMatch(/^All these rooms have finished/);
    expect(finishedNote(2, 5)).toMatch(/^2 of these rooms have finished/);
  });
});
