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

/**
 * Slice 1 transport: polling (protocol §7.3). One request in flight, timeout, full-jitter backoff.
 * SSE replaces this in the next slice.
 */
export function usePoll<T extends { version?: number }>(path: string, everyMs = 2000): Poll<T> {
  const [data, setData] = useState<T | null>(null);
  const [online, setOnline] = useState(true);
  const [unauthorized, setUnauthorized] = useState(false);
  const version = useRef(-1);

  useEffect(() => {
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
  }, [path, everyMs]);

  return { data, setData, online, unauthorized };
}
