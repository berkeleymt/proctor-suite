import { useState } from "react";
import type { Snapshot } from "../api";
import type { Status } from "../screens/adminActions";

/**
 * Renders the real Timers page without a server. Test files mock `useLive` with `useFakeLive`
 * (see admin-page.test.tsx); `live.set(rooms)` then plays the part of a server update.
 */

type Rooms = { rooms: Snapshot[]; presence: []; version: number };

export const live: { initial: Rooms; set: (rooms: Snapshot[]) => void } = {
  initial: { rooms: [], presence: [], version: 1 },
  set: () => {
    throw new Error("Render <Admin /> first.");
  },
};

export function useFakeLive() {
  const [data, setData] = useState<Rooms | null>(live.initial);
  live.set = (rooms) => setData((d) => ({ ...d!, rooms }));
  return { data, setData, online: true, unauthorized: false };
}

/** A room in one timer state, shaped like the server's snapshot. */
export function room(name: string, status: Status, over: Partial<Snapshot> = {}): Snapshot {
  const now = Date.now();
  return {
    room_id: name.toLowerCase().replaceAll(" ", "-"),
    room_name: name,
    test_name: "Individual Round",
    session_id: `session-${name}`,
    version: 1,
    server_time_ms: now,
    timer: {
      status,
      duration_ms: 3_600_000,
      adjust_total_ms: 0,
      elapsed_banked_ms: status === "PAUSED" ? 600_000 : status === "ENDED" ? 3_600_000 : 0,
      running_since_ms: status === "RUNNING" ? now : null,
    },
    deleted: false,
    doc_url: null,
    display: { timer_zoom_pct: 80, clar_size: "auto", timer_zoom_at_ms: null, clar_size_at_ms: null },
    clarifications: [],
    students_out: 0,
    bathroom_out: [],
    bathroom_back: [],
    ...over,
  } as Snapshot;
}

/** One room in each timer state, in the order a test day goes. */
export const ONE_OF_EACH: Snapshot[] = [
  room("Evans 10", "NOT_PERMITTED"),
  room("Evans 20", "PERMITTED"),
  room("Evans 30", "RUNNING"),
  room("Evans 40", "PAUSED"),
  room("Evans 50", "ENDED"),
];

/** Start the page with these rooms. Call before render(<Admin />). */
export function withRooms(rooms: Snapshot[]) {
  live.initial = { rooms, presence: [], version: 1 };
}

/** The same room, now in another state (as a server update would carry it). */
export const moved = (s: Snapshot, status: Status) => ({ ...room(s.room_name, status), version: s.version + 1 });
