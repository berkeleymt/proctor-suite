import type { components } from "./api-types";

export type Snapshot = components["schemas"]["RoomSnapshot"];
export type Command = components["schemas"]["CommandResponse"];
export type RoomPresence = components["schemas"]["RoomPresence"];
export type SurfacePresence = components["schemas"]["SurfacePresence"];
export type RoomOption = components["schemas"]["LoginRoomOption"];
export type Identity = components["schemas"]["RoomIdentity"] | components["schemas"]["StaffIdentity"];

const TIMEOUT_MS = 10_000; // protocol REQUEST_TIMEOUT_S
const BACKOFF_BASE_S = 1;
const BACKOFF_CAP_S = 30;

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** One request, with a timeout (invariant 2). 304 resolves to null. */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T | null> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), TIMEOUT_MS);
  const post = ["POST", "PATCH", "DELETE"].includes(init.method ?? "GET");
  try {
    const r = await fetch(path, {
      ...init,
      signal: ctl.signal,
      credentials: "same-origin",
      headers: { ...(post ? { "Content-Type": "application/json", "X-Proctor-Client": "web" } : {}), ...init.headers },
    });
    if (r.status === 304 || r.status === 204) return null;
    if (!r.ok) {
      const d = await r.json().catch(() => null);
      throw new ApiError(r.status, d?.detail?.message ?? `Request failed (${r.status})`);
    }
    return (await r.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const patch = <T>(path: string, body: unknown) => api<T>(path, { method: "PATCH", body: JSON.stringify(body) });

export const del = <T>(path: string) => api<T>(path, { method: "DELETE" });

export const backoff = (attempt: number) => Math.random() * Math.min(BACKOFF_CAP_S, BACKOFF_BASE_S * 2 ** attempt) * 1000;

// ---- clock sync (protocol §4): keep the lowest-RTT of the last 8 samples ----
let anchorServer = Date.now();
let anchorPerf = performance.now();
const samples: { rtt: number; server: number; perf: number }[] = [];

export const serverNow = () => anchorServer + (performance.now() - anchorPerf);

export async function syncClock(): Promise<void> {
  const t0 = performance.now();
  const r = await api<{ server_time_ms: number }>("/api/time");
  const t1 = performance.now();
  if (!r) return;
  samples.push({ rtt: t1 - t0, server: r.server_time_ms + (t1 - t0) / 2, perf: t1 });
  if (samples.length > 8) samples.shift();
  const best = samples.reduce((a, b) => (b.rtt < a.rtt ? b : a));
  anchorServer = best.server;
  anchorPerf = best.perf;
}

export function remainingMs(s: Snapshot, now = serverNow()): number {
  const t = s.timer;
  const running = t.running_since_ms != null ? now - t.running_since_ms : 0;
  return Math.max(0, t.duration_ms + t.adjust_total_ms - t.elapsed_banked_ms - running);
}

export function fmt(ms: number): string {
  const s = Math.ceil(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  return `${h}:${m}:${String(s % 60).padStart(2, "0")}`;
}

/** Send one command. The same command_id is reused on retry (invariant 3). */
export async function sendCommand(
  type: "permit" | "start" | "pause" | "resume" | "end" | "adjust",
  snap: Snapshot,
  extra: { delta_ms?: number } = {},
): Promise<Command> {
  const deviceKey = "device_id";
  const device_id = localStorage.getItem(deviceKey) ?? crypto.randomUUID();
  localStorage.setItem(deviceKey, device_id);
  const body = {
    type, command_id: crypto.randomUUID(), device_id, room_id: snap.room_id,
    session_id: snap.session_id, claimed_at_ms: Math.round(serverNow()), ...extra,
  };
  let last: unknown;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      return (await post<Command>("/api/commands", body))!;
    } catch (e) {
      if (e instanceof ApiError) throw e; // a real answer: don't retry
      last = e;
      await new Promise((r) => setTimeout(r, backoff(attempt)));
    }
  }
  throw last;
}
