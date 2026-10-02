import { useEffect, useRef, useState } from "react";
import { ApiError, post, type RosterData, type Snapshot } from "../api";
import { AdminBar, Sheet } from "../components/ui";
import { dropRoom, mergeRooms, stampOf, useClock, useDebounced, useFetched, useLive } from "../hooks";
import { go } from "../main";
import { usePageTitle } from "../brand";

const clock = (ms: number) => new Date(ms).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
const why = (e: unknown) => (e instanceof ApiError ? e.message : "Couldn't reach the server. Try again.");
const NO_ROOM = "\u0000none"; // select value for "students with no room"

/** The roster: who each student ID is. Synced from ContestDojo (token and event ID are set on /super). */
export function Roster() {
  usePageTitle("Roster");
  useClock();
  const live = useLive<{ rooms: Snapshot[]; version?: number }>("/api/staff/rooms", "/api/staff/stream", mergeRooms, 4000, { room_removed: dropRoom });
  const [room, setRoom] = useState("");
  const [q, setQ] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [msg, setMsg] = useState<{ text: string; bad: boolean } | null>(null);
  const query = useDebounced(q.trim());
  const params = new URLSearchParams();
  if (room) params.set("room", room === NO_ROOM ? "" : room);
  if (query) params.set("q", query);
  const { data, refresh } = useFetched<RosterData>(`/api/staff/roster?${params}`, stampOf(live.data?.rooms));
  useEffect(() => {
    if (live.unauthorized) go("/login");
  }, [live.unauthorized]);
  if (!data) return <main className="center" />;

  async function sync() {
    setSyncing(true);
    setMsg(null);
    try {
      const r = (await post<{ count: number }>("/api/staff/roster/sync"))!;
      setMsg({ text: `Synced ${r.count.toLocaleString()} students from ContestDojo.`, bad: false });
      await refresh();
    } catch (e) {
      setMsg({ text: why(e), bad: true });
    } finally {
      setSyncing(false);
    }
  }

  const empty = data.total === 0;
  const stamp = data.synced_at_ms ? `${data.source === "contestdojo" ? "Synced from ContestDojo" : "Synced from ContestDojo"} ${clock(data.synced_at_ms)}` : "No roster yet";
  return (
    <main className="admin">
      <AdminBar active="roster" online={live.online} summary={`${data.total.toLocaleString()} students · ${stamp}`}>
        <button className={empty ? "primary" : ""} disabled={syncing} onClick={sync}>
            {syncing ? "Syncing…" : "Sync"}
          </button>
        {!empty && (
          <button className="bad" onClick={() => setClearing(true)}>
            Clear roster…
          </button>
        )}
      </AdminBar>
      {msg && (
        <p className={msg.bad ? "error note" : "muted note"} role={msg.bad ? "alert" : "status"}>
          {msg.text}
        </p>
      )}
      {empty ? (
        <div className="center-text block-empty">
          <h2>No roster yet</h2>
          <p className="muted">Press Sync to pull every student from ContestDojo. Set the API token and event ID on the /super page first.</p>
          <button className="primary" disabled={syncing} onClick={sync}>
            {syncing ? "Syncing…" : "Sync"}
          </button>
        </div>
      ) : (
        <>
          <div className="logbar" role="search">
            <label className="inline">
              Room
              <select value={room} onChange={(e) => setRoom(e.target.value)}>
                <option value="">All rooms</option>
                {data.rooms.map((r) => (
                  <option key={r}>{r}</option>
                ))}
                <option value={NO_ROOM}>No room yet</option>
              </select>
            </label>
            <input type="search" aria-label="Search name, ID or school" placeholder="Search name, ID or school…" value={q} onChange={(e) => setQ(e.target.value)} />
            <span className="grow" />
            <span className="muted">
              {data.matching.toLocaleString()} {data.matching === 1 ? "student" : "students"} · {data.out_now} out
            </span>
          </div>
          <div className="table roster">
            <div className="tr th">
              <span>Name</span>
              <span>ID</span>
              <span>School / team</span>
              <span>Parent / coach contact</span>
              <span>Status</span>
            </div>
            {data.students.length === 0 && <p className="muted empty">No students match.</p>}
            {data.students.map((s) => (
              <div className="tr" key={s.id}>
                <span>{s.name || <span className="muted">(no name)</span>}</span>
                <span className="mono">{s.id}</span>
                <span className="muted">{[s.school, s.team].filter(Boolean).join(" · ")}</span>
                <span className="muted">{s.contact}</span>
                <span className="when" data-late={s.out_since_ms !== null}>
                  {s.out_since_ms !== null ? `Out since ${clock(s.out_since_ms)}` : "Present"}
                </span>
              </div>
            ))}
          </div>
          {data.matching > data.students.length && <p className="muted note">Showing the first {data.students.length}. Search or pick a room to narrow it down.</p>}
        </>
      )}
      {clearing && (
        <ClearSheet
          count={data.total}
          onClose={() => setClearing(false)}
          onDone={(n) => {
            setClearing(false);
            setMsg({ text: `Cleared ${n.toLocaleString()} students from the roster.`, bad: false });
            void refresh();
          }}
        />
      )}
    </main>
  );
}

/** Wipes names and contacts of minors. Type DELETE, like every other destructive action here. */
function ClearSheet({ count, onClose, onDone }: { count: number; onClose: () => void; onDone: (n: number) => void }) {
  const [typed, setTyped] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function go() {
    if (typed !== "DELETE") return;
    setBusy(true);
    setErr("");
    try {
      onDone((await post<{ count: number }>("/api/staff/roster/clear"))!.count);
    } catch (e) {
      setErr(why(e));
      setBusy(false);
    }
  }
  return (
    <Sheet title={`Clear all ${count.toLocaleString()} students?`} onClose={onClose} onSubmit={go}>
      <p className="muted">
        This removes every name, school and contact from the roster for good. Proctors will see only IDs until you import again. Bathroom records stay, without names.
      </p>
      <label>
        Type DELETE to confirm
        <input autoFocus value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
      </label>
      <p className="error" role="alert" hidden={!err}>
        {err}
      </p>
      <div className="row">
        <button type="button" onClick={onClose}>
          Cancel
        </button>
        <button className="danger" disabled={typed !== "DELETE" || busy}>
          {busy ? "Clearing…" : "Clear roster"}
        </button>
      </div>
    </Sheet>
  );
}
