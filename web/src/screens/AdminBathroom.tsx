import { useEffect, useState } from "react";
import { api, ApiError, post, serverNow, type BathroomEntry, type BathroomLogData, type Snapshot } from "../api";
import { AdminBar, Sheet } from "../components/ui";
import { dropRoom, mergeRooms, stampOf, useClock, useDebounced, useFetched, useLive, useTick } from "../hooks";
import { go } from "../main";
import { usePageTitle } from "../brand";

type View = "out" | "returned" | "all";
type Ask = { kind: "delete" | "empty"; ids: string[] | null; count: number; out: number };
const LATE_MIN = 10; // same threshold as the proctor's page
const EXPORT_LIMIT = 5000; // protocol MAX_ADMIN_BATHROOM_EXPORT

const clock = (ms: number) => new Date(ms).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
const why = (e: unknown) => (e instanceof ApiError ? e.message : "Couldn't reach the server. Try again.");
const span = (ms: number) => {
  const m = Math.floor(ms / 60_000);
  return m < 1 ? "under 1 min" : m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`;
};

/** Proctors record, admins look and (carefully) delete. Deleting hides, like rooms and clarifications. */
export function AdminBathroom() {
  usePageTitle("Bathroom");
  useClock();
  useTick();
  const live = useLive<{ rooms: Snapshot[]; version?: number }>("/api/staff/rooms", "/api/staff/stream", mergeRooms, 4000, { room_removed: dropRoom });
  const [view, setView] = useState<View>("out");
  const [room, setRoom] = useState("");
  const [q, setQ] = useState("");
  const [showDeleted, setShowDeleted] = useState(false);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [ask, setAsk] = useState<Ask | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const query = useDebounced(q.trim());
  const params = new URLSearchParams({ status: view });
  if (room) params.set("room_id", room);
  if (query) params.set("q", query);
  if (showDeleted) params.set("deleted", "true");
  const { data, refresh } = useFetched<BathroomLogData>(`/api/staff/bathroom?${params}`, stampOf(live.data?.rooms));
  useEffect(() => {
    if (live.unauthorized) go("/login");
  }, [live.unauthorized]);

  // Ticks only ever apply to records you can still see.
  const entries = data?.entries ?? [];
  const alive = entries.filter((e) => !e.deleted);
  const gone = entries.filter((e) => e.deleted);
  useEffect(() => {
    const vis = new Set(entries.filter((e) => !e.deleted).map((e) => e.id));
    setSel((cur) => (cur.size && [...cur].some((id) => !vis.has(id)) ? new Set([...cur].filter((id) => vis.has(id))) : cur));
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!data || !live.data) return <main className="center" />;

  const rooms = [...live.data.rooms].sort((a, b) => a.room_name.localeCompare(b.room_name, undefined, { numeric: true }));
  const filtering = !!room || !!query;
  const allOn = alive.length > 0 && alive.every((e) => sel.has(e.id));
  const toggle = (id: string) =>
    setSel((cur) => {
      const n = new Set(cur);
      if (!n.delete(id)) n.add(id);
      return n;
    });
  const outIn = (ids: string[] | null) => (ids ? alive.filter((e) => ids.includes(e.id)) : alive).filter((e) => e.back_ms === null).length;

  async function run(ids: string[] | null, action: "delete" | "restore" | "empty") {
    setAsk(null);
    setBusy(true);
    setErr("");
    try {
      const r = await post<{ changed: number; skipped: number }>("/api/staff/bathroom/action", ids ? { action, ids } : { action, all: true });
      if (r?.skipped) setErr(`${r.skipped} not restored: that student has gone out again since.`);
      setSel(new Set());
      await refresh();
    } catch (e) {
      setErr(why(e));
    } finally {
      setBusy(false);
    }
  }
  const restore = (ids: string[] | null) => run(ids, "restore");

  /** Everything in the log for the chosen room, all statuses: the "after the test" record. */
  async function exportCsv() {
    setErr("");
    try {
      const p = new URLSearchParams({ status: "all", limit: String(EXPORT_LIMIT) });
      if (room) p.set("room_id", room);
      const r = (await api<BathroomLogData>(`/api/staff/bathroom?${p}`))!;
      const cell = (v: string | number | null) => `"${String(v ?? "").replace(/"/g, '""')}"`;
      const when = (ms: number | null) => (ms === null ? "" : new Date(ms).toLocaleString());
      const rows = [["Student ID", "Name", "School", "Room", "Left", "Back", "Minutes"], ...r.entries.map((e) => [e.student_id, e.student_name, e.school, e.room_name, when(e.left_ms), when(e.back_ms), e.back_ms === null ? "" : Math.round((e.back_ms - e.left_ms) / 60_000)])];
      const url = URL.createObjectURL(new Blob(["\ufeff" + rows.map((x) => x.map(cell).join(",")).join("\r\n")], { type: "text/csv" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `bathroom-log-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      if (r.truncated) setErr(`The file has the latest ${EXPORT_LIMIT.toLocaleString()} records. Export one room at a time to get the rest.`);
    } catch (e) {
      setErr(why(e));
    }
  }

  const row = (e: BathroomEntry) => {
    const out = e.back_ms === null;
    const m = Math.floor(((out ? serverNow() : e.back_ms!) - e.left_ms) / 60_000);
    return (
      <div className={`tr${e.deleted ? " gone" : ""}`} key={e.id}>
        {e.deleted ? <span /> : <input type="checkbox" aria-label={`Select ${e.student_id}`} checked={sel.has(e.id)} onChange={() => toggle(e.id)} />}
        <span title={e.school ?? undefined}>
          <strong className="mono">{e.student_id}</strong>
          {e.student_name && <span className="muted"> · {e.student_name}</span>}
        </span>
        <span>{e.room_name}</span>
        <span className="mono">{clock(e.left_ms)}</span>
        <span className="mono">{out ? "–" : clock(e.back_ms!)}</span>
        <span className="when" data-late={!e.deleted && out && m >= LATE_MIN}>
          {out ? `Out ${span(serverNow() - e.left_ms)}` : span(e.back_ms! - e.left_ms)}
        </span>
        <span className="row">
          {e.deleted ? (
            <>
              <button onClick={() => restore([e.id])}>Restore</button>
              <button className="bad" onClick={() => setAsk({ kind: "empty", ids: [e.id], count: 1, out: 0 })}>
                Empty…
              </button>
            </>
          ) : (
            <button className="bad" onClick={() => setAsk({ kind: "delete", ids: [e.id], count: 1, out: out ? 1 : 0 })}>
              Delete…
            </button>
          )}
        </span>
      </div>
    );
  };

  const nothing = view === "out" ? "Nobody is out right now." : view === "returned" ? "Nobody has come back yet." : "Nothing has been logged yet.";
  return (
    <main className="admin">
      <AdminBar
        active="bathroom"
        online={live.online}
        summary={`${data.out_now} out now · ${data.returned} returned`}
        deleted={{ count: data.deleted, shown: showDeleted, toggle: () => setShowDeleted(!showDeleted) }}
      />
      <div className="logbar" role="search">
        <label className="inline">
          Room
          <select value={room} onChange={(e) => setRoom(e.target.value)}>
            <option value="">All rooms</option>
            {rooms.map((r) => (
              <option key={r.room_id} value={r.room_id}>
                {r.room_name}
                {r.deleted ? " (deleted)" : ""}
              </option>
            ))}
          </select>
        </label>
        <div className="chips" role="group" aria-label="Show">
          {(["out", "returned", "all"] as const).map((v) => (
            <button key={v} className="chip" aria-pressed={view === v} onClick={() => setView(v)}>
              {v === "out" ? `Out now (${data.out_now})` : v === "returned" ? `Returned (${data.returned})` : "All"}
            </button>
          ))}
        </div>
        <input type="search" aria-label="Search student ID, name or room" placeholder="Search student ID or name…" value={q} onChange={(e) => setQ(e.target.value)} />
        <span className="grow" />
        <button onClick={exportCsv} title="Every record for the chosen room, any status">
          Export CSV
        </button>
        <button className="bad" disabled={busy || data.out_now + data.returned === 0} onClick={() => setAsk({ kind: "delete", ids: null, count: data.out_now + data.returned, out: data.out_now })}>
          Delete all…
        </button>
      </div>
      {sel.size > 0 && (
        <div className="bulk" role="toolbar" aria-label="Selected records">
          <strong>{sel.size} selected</strong>
          <button className="bad" disabled={busy} onClick={() => setAsk({ kind: "delete", ids: [...sel], count: sel.size, out: outIn([...sel]) })}>
            Delete…
          </button>
        </div>
      )}
      {showDeleted && gone.length > 0 && (
        <div className="bulk quiet" role="toolbar" aria-label="Deleted records">
          <strong>{data.deleted} deleted</strong>
          <button disabled={busy} onClick={() => restore(null)}>
            Restore all
          </button>
          <button className="bad" disabled={busy} onClick={() => setAsk({ kind: "empty", ids: null, count: data.deleted, out: 0 })}>
            Empty all…
          </button>
        </div>
      )}
      <p className="error" role="alert" hidden={!err}>
        {err}
      </p>
      <div className="table log">
        <div className="tr th">
          <input
            type="checkbox"
            aria-label={filtering ? "Select all shown records" : "Select all records"}
            checked={allOn}
            ref={(el) => {
              if (el) el.indeterminate = sel.size > 0 && !allOn;
            }}
            onChange={() => setSel(allOn ? new Set() : new Set(alive.map((e) => e.id)))}
          />
          <span>Student</span>
          <span>Room</span>
          <span>Out</span>
          <span>Back</span>
          <span>Duration</span>
          <span />
        </div>
        {alive.length === 0 && gone.length === 0 && <p className="muted empty">{filtering ? "No records match." : nothing}</p>}
        {alive.map(row)}
        {gone.map(row)}
      </div>
      {data.truncated && <p className="muted note">Showing the first {entries.length.toLocaleString()}. Search or pick a room to narrow it down.</p>}
      {ask && <AskSheet ask={ask} onClose={() => setAsk(null)} onGo={() => run(ask.ids, ask.kind)} />}
    </main>
  );
}

/** Delete asks you to type DELETE (it hides records from proctors); Empty is permanent and says so. */
function AskSheet({ ask, onClose, onGo }: { ask: Ask; onClose: () => void; onGo: () => void }) {
  const [typed, setTyped] = useState("");
  const many = ask.count === 1 ? "record" : "records";
  if (ask.kind === "empty")
    return (
      <Sheet title={`Empty ${ask.count} deleted ${many}?`} onClose={onClose}>
        <p className="muted">This removes {ask.count === 1 ? "it" : "them"} from the database for good. You can&apos;t undo this. Use Restore if you might need {ask.count === 1 ? "it" : "them"}.</p>
        <div className="row">
          <button onClick={onClose}>Cancel</button>
          <button className="danger" onClick={onGo}>
            Empty
          </button>
        </div>
      </Sheet>
    );
  return (
    <Sheet title={ask.ids === null ? `Delete all ${ask.count} records?` : `Delete ${ask.count} ${many}?`} onClose={onClose} onSubmit={onGo}>
      <p className="muted">
        {ask.count === 1 ? "It disappears" : "They disappear"} from this list and from the proctors&apos; pages. {ask.out > 0 && `${ask.out} ${ask.out === 1 ? "student is" : "students are"} out right now and will vanish from the proctor's list. `}You can bring {ask.count === 1 ? "it" : "them"} back from &ldquo;Show deleted&rdquo;.
      </p>
      <label>
        Type DELETE to confirm
        <input autoFocus value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
      </label>
      <div className="row">
        <button type="button" onClick={onClose}>
          Cancel
        </button>
        <button className="danger" disabled={typed !== "DELETE"}>
          Delete {many}
        </button>
      </div>
    </Sheet>
  );
}
