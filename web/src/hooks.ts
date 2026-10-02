import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { api, ApiError, backoff, syncClock, type Snapshot } from "./api";

/** Re-renders every 250 ms (protocol TIMER_TICK_MS). Time is derived, never decremented. */
export function useTick() {
  const [, set] = useState(0);
  useEffect(() => {
    const id = setInterval(() => set((n) => n + 1), 250);
    return () => clearInterval(id);
  }, []);
}

/** Clock sync on mount, every 60 s, and when the tab wakes. */
export function useClock() {
  useEffect(() => {
    const go = () => syncClock().catch(() => {});
    go();
    const id = setInterval(go, 60_000);
    const vis = () => document.visibilityState === "visible" && go();
    document.addEventListener("visibilitychange", vis);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", vis);
    };
  }, []);
}

export interface Poll<T> {
  data: T | null;
  setData: Dispatch<SetStateAction<T | null>>;
  online: boolean;
  unauthorized: boolean;
}

const DEAD_AFTER_MS = 35_000; // protocol STREAM_DEAD_AFTER_S

/**
 * Live data (protocol §7-§8): Server-Sent Events when they work, polling only while they don't.
 * - The stream is reconnected by us (never EventSource's own retry) with full-jitter backoff.
 * - Silence for 35 s (no snapshot, no heartbeat) means the stream is dead.
 * - Polling runs only while the stream is down, so first paint is fast and a proxy that blocks
 *   SSE still gives a working (slower) screen.
 * `merge` folds a streamed snapshot into the current data; it must ignore stale versions.
 */
export function useLive<T extends { version?: number }>(
  pollPath: string,
  streamPath: string,
  merge: (prev: T | null, snap: Snapshot) => T | null,
  everyMs = 2000,
): Poll<T> {
  const [data, setData] = useState<T | null>(null);
  const [live, setLive] = useState(false);
  const [pollOk, setPollOk] = useState(true);
  const [unauthorized, setUnauthorized] = useState(false);
  const mergeRef = useRef(merge);
  mergeRef.current = merge;

  useEffect(() => {
    let stop = false;
    let es: EventSource | undefined;
    let retry: number;
    let dead: number;
    let fails = 0;
    const open = () => {
      if (stop) return;
      es = new EventSource(streamPath);
      const alive = () => {
        clearTimeout(dead);
        dead = window.setTimeout(fail, DEAD_AFTER_MS);
        fails = 0;
        setLive(true);
      };
      const fail = () => {
        es?.close();
        clearTimeout(dead);
        setLive(false);
        if (!stop) retry = window.setTimeout(open, backoff(fails++));
      };
      es.addEventListener("snapshot", (e) => {
        alive();
        setData((prev) => mergeRef.current(prev, JSON.parse((e as MessageEvent).data)));
      });
      es.addEventListener("heartbeat", alive);
      es.onerror = fail;
    };
    open();
    return () => {
      stop = true;
      es?.close();
      clearTimeout(retry);
      clearTimeout(dead);
    };
  }, [streamPath]);

  const polled = usePoll<T>(pollPath, everyMs, !live);
  useEffect(() => {
    if (polled.data) setData((prev) => (prev && (prev.version ?? 0) > (polled.data!.version ?? 0) && "room_id" in prev ? prev : polled.data));
  }, [polled.data]);
  useEffect(() => {
    if (polled.unauthorized) setUnauthorized(true);
  }, [polled.unauthorized]);
  useEffect(() => setPollOk(polled.online), [polled.online]);

  return { data, setData, online: live || pollOk, unauthorized };
}

/** Whole-room stream: keep the newest version of one room. */
export const mergeRoom = (prev: Snapshot | null, snap: Snapshot): Snapshot =>
  prev && prev.version > snap.version ? prev : snap;

/** Staff stream: one snapshot per room; replace that room, keep the list sorted by name. */
export function mergeRooms(prev: { rooms: Snapshot[] } | null, snap: Snapshot) {
  const rooms = prev?.rooms ?? [];
  const old = rooms.find((r) => r.room_id === snap.room_id);
  if (old && old.version > snap.version) return prev;
  const next = [...rooms.filter((r) => r.room_id !== snap.room_id), snap];
  return { ...prev, rooms: next.sort((a, b) => a.room_name.localeCompare(b.room_name)) };
}

/** Polling transport (protocol §7.3). One request in flight, timeout, full-jitter backoff. */
export function usePoll<T extends { version?: number }>(path: string, everyMs = 2000, enabled = true): Poll<T> {
  const [data, setData] = useState<T | null>(null);
  const [online, setOnline] = useState(true);
  const [unauthorized, setUnauthorized] = useState(false);
  const version = useRef(-1);

  useEffect(() => {
    if (!enabled) return;
    let stop = false;
    let timer: number;
    let fails = 0;
    const loop = async () => {
      let wait = everyMs;
      try {
        const r = await api<T>(`${path}${path.includes("?") ? "&" : "?"}since_version=${version.current}`);
        if (r) {
          version.current = r.version ?? -1;
          setData(r);
        }
        fails = 0;
        setOnline(true);
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) {
          setUnauthorized(true);
          return;
        }
        setOnline(false);
        wait = backoff(fails++);
      }
      if (!stop) timer = window.setTimeout(loop, wait);
    };
    loop();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [path, everyMs, enabled]);

  return { data, setData, online, unauthorized };
}
