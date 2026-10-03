import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { ApiError, backoff, patch, serverNow, type Snapshot } from "./api";
import type { components } from "./api-types";
import { mergeRoom } from "./hooks";

/**
 * Projector sizes, one per room (protocol §7.9, ADR 0019). The server holds them; the proctor page
 * changes them. Each click is first saved in this browser, so a display window in the same browser
 * follows at once, even with the server down. A small queue then sends it (one request in flight,
 * full-jitter backoff), and the server keeps the last click per field.
 */

export type Display = Snapshot["display"];
export type TimerPct = Display["timer_zoom_pct"];
export type ClarSize = Display["clar_size"];
type Request = components["schemas"]["SetDisplayRequest"];

// Every allowed timer size, checked against the contract: a missing or extra key won't compile.
const PCTS: Record<TimerPct, true> = { 40: true, 50: true, 60: true, 70: true, 80: true, 90: true, 100: true };
export const TIMER_PCTS = (Object.keys(PCTS).map(Number) as TimerPct[]).sort((a, b) => a - b);
export const TIMER_PCT_DEFAULT: TimerPct = 80; // contract DISPLAY_TIMER_ZOOM_DEFAULT
export const CLAR_STEPS = 8; // contract DISPLAY_CLAR_STEPS (a test checks it against openapi.json)

export interface Values {
  timer_zoom_pct: TimerPct;
  clar_size: ClarSize;
}
export type Field = keyof Values;
const FIELDS: Field[] = ["timer_zoom_pct", "clar_size"];
const AT: Record<Field, "timer_zoom_at_ms" | "clar_size_at_ms"> = { timer_zoom_pct: "timer_zoom_at_ms", clar_size: "clar_size_at_ms" };

/** A click saved in this browser. `ack` = the room version that includes it, once the server has it. */
export interface Pending<F extends Field = Field> {
  value: Values[F];
  at: number;
  id: string;
  ack?: number;
}
export type Local = { [F in Field]?: Pending<F> };

const key = (roomId: string) => `display:${roomId}`;
// Worth sending again: signed out (it goes once the proctor signs back in), timeout, rate limit.
const RETRY = new Set([401, 408, 429]);

const valid: Record<Field, (v: unknown) => boolean> = {
  timer_zoom_pct: (v) => TIMER_PCTS.includes(v as TimerPct),
  clar_size: (v) => v === "auto" || (Number.isInteger(v) && (v as number) >= 0 && (v as number) < CLAR_STEPS),
};

/** What this browser saved for a room. Anything malformed is ignored, never thrown. */
export function readLocal(roomId: string): Local {
  try {
    const raw = JSON.parse(localStorage.getItem(key(roomId)) ?? "{}");
    const out: Local = {};
    for (const f of FIELDS) {
      const p = raw?.[f];
      if (p && valid[f](p.value) && Number.isFinite(p.at) && typeof p.id === "string" && (p.ack === undefined || Number.isFinite(p.ack))) {
        (out as Record<Field, Pending>)[f] = { value: p.value, at: p.at, id: p.id, ...(p.ack === undefined ? {} : { ack: p.ack }) };
      }
    }
    return out;
  } catch {
    return {};
  }
}

function writeLocal(roomId: string, local: Local) {
  try {
    localStorage.setItem(key(roomId), JSON.stringify(local));
  } catch {
    /* private mode or full: the click still goes to the server */
  }
}

/**
 * What the projector should show: the server's value, unless this browser holds a click the
 * server hasn't confirmed yet (and nothing newer is on the server), or one it has confirmed but
 * this page hasn't received yet.
 */
export function effective(s: Snapshot, local: Local): Values {
  const pick = <F extends Field>(f: F): Values[F] => {
    const p = local[f] as Pending<F> | undefined;
    const server = s.display[f] as Values[F];
    if (!p) return server;
    if (p.ack === undefined) return p.at > (s.display[AT[f]] ?? -Infinity) ? p.value : server;
    return s.version < p.ack ? p.value : server;
  };
  return { timer_zoom_pct: pick("timer_zoom_pct"), clar_size: pick("clar_size") };
}

/** This browser's saved clicks for a room, kept current when another window changes them. */
function useLocal(roomId: string): [Local, Dispatch<SetStateAction<Local>>] {
  const [local, setLocal] = useState<Local>(() => readLocal(roomId));
  useEffect(() => {
    setLocal(readLocal(roomId));
    const sync = (e: StorageEvent) => e.key === key(roomId) && setLocal(readLocal(roomId));
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, [roomId]);
  return [local, setLocal];
}

/** The projector: just reads. */
export function useDisplayValues(s: Snapshot): Values {
  const [local] = useLocal(s.room_id);
  return effective(s, local);
}

/** The proctor page: reads, and sets (saved here first, then sent). */
export function useDisplayControl(s: Snapshot, setData: Dispatch<SetStateAction<Snapshot | null>>) {
  const roomId = s.room_id;
  const [local, setLocal] = useLocal(roomId);
  const [error, setError] = useState("");
  const busy = useRef(false);
  const fails = useRef(0);
  const [kick, setKick] = useState(0);
  const alive = useRef(true);
  useEffect(() => () => void (alive.current = false), []);

  /** Change one saved click, but only if it is still the one we mean (`id`). */
  const settle = useCallback(
    (f: Field, id: string, next: (p: Pending) => Pending | undefined) => {
      const cur = readLocal(roomId);
      const p = cur[f];
      if (!p || p.id !== id) return;
      const n = next(p);
      const out = { ...cur, [f]: n };
      if (!n) delete out[f];
      writeLocal(roomId, out);
      setLocal(out);
    },
    [roomId, setLocal],
  );

  const set = <F extends Field>(f: F, value: Values[F]) => {
    const cur = readLocal(roomId);
    const out = { ...cur, [f]: { value, at: Math.round(serverNow()), id: crypto.randomUUID() } };
    writeLocal(roomId, out);
    setLocal(out);
  };

  // The queue: send unconfirmed clicks one at a time (invariant 2), oldest field first.
  useEffect(() => {
    if (busy.current) return;
    const f = FIELDS.find((x) => local[x] && local[x]!.ack === undefined);
    if (!f) return;
    const p = local[f]!;
    busy.current = true;
    const body: Request = { command_id: p.id, claimed_at_ms: p.at, [f]: p.value };
    (async () => {
      try {
        const r = await patch<Snapshot>(`/api/rooms/${roomId}/display`, body);
        fails.current = 0;
        if (r) {
          setData((prev) => mergeRoom(prev, r));
          settle(f, p.id, (x) => ({ ...x, ack: r.version }));
        }
        setError("");
      } catch (e) {
        if (e instanceof ApiError && !RETRY.has(e.status) && e.status < 500) {
          settle(f, p.id, () => undefined); // the server said no: retrying won't help
          setError(`Couldn't change the projector: ${e.message}`);
        } else {
          setError("Not saved yet. The projector in this browser shows it; other screens will follow when the connection is back.");
          await new Promise((ok) => setTimeout(ok, backoff(fails.current++)));
        }
      } finally {
        busy.current = false;
        if (alive.current) setKick((n) => n + 1);
      }
    })();
  }, [local, kick, roomId, setData, settle]);

  return { values: effective(s, local), set, error };
}
