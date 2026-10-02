import { useEffect, useRef, useState } from "react";
import { ApiError, del, fmt, patch, post, remainingMs, sendCommand, serverNow, type RoomPresence, type Snapshot, type SurfacePresence } from "../api";
import { AdminBar, Sheet } from "../components/ui";
import { dropRoom, mergePresence, mergeRooms, useClock, useLive, useTick } from "../hooks";
import { go } from "../main";
import { usePageTitle } from "../brand";
import { label } from "./Display";

type Rooms = { rooms: Snapshot[]; presence?: RoomPresence[]; version?: number };
type Kind = "permit" | "start" | "pause" | "resume" | "adjust" | "reset";
type Action = "permit" | "start" | "adjust" | "pause" | "resume" | "reset";
type Confirm = { title: string; detail: string; confirm: string; run: () => void };
type Filters = { room: string; test: string; status: string; dur: string; dev: string };
const NO_FILTER: Filters = { room: "", test: "", status: "", dur: "", dev: "" };
const STATUSES = ["NOT_PERMITTED", "PERMITTED", "RUNNING", "PAUSED", "ENDED"] as const;
const mins = (s: Snapshot) => Math.round(s.timer.duration_ms / 60_000);
const started = (s: Snapshot) => !["NOT_PERMITTED", "PERMITTED"].includes(s.timer.status);
const inProgress = (s: Snapshot) => ["RUNNING", "PAUSED"].includes(s.timer.status);
const clock = (ms: number) => new Date(ms).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
const why = (e: unknown) => (e instanceof ApiError ? e.message : "Couldn't reach the server. Try again.");

/** What a bulk action would do to one room: the commands to send, or none (skipped). */
function plan(action: Action, s: Snapshot): Kind[] {
  const st = s.timer.status;
  if (action === "adjust") return st === "ENDED" ? [] : ["adjust"];
  if (action === "pause") return st === "RUNNING" ? ["pause"] : [];
  if (action === "resume") return st === "PAUSED" ? ["resume"] : [];
  if (action === "reset") return st === "PAUSED" || st === "ENDED" ? ["reset"] : [];
  if (action === "permit") return st === "NOT_PERMITTED" ? ["permit"] : [];
  return st === "NOT_PERMITTED" ? ["permit", "start"] : st === "PERMITTED" ? ["start"] : [];
}

/** Run `fn` over items, a few at a time, so 50 rooms don't open 50 connections (invariant 2). */
async function pool<T>(items: T[], fn: (t: T) => Promise<string>, size = 6) {
  const queue = [...items];
  const done: T[] = [];
  const fails: string[] = [];
  await Promise.all(
    Array.from({ length: Math.min(size, queue.length) }, async () => {
      for (let t = queue.shift(); t; t = queue.shift()) {
        const e = await fn(t);
        if (e) fails.push(e);
        else done.push(t);
      }
    }),
  );
  return { done, fails };
}

/** Is a proctor / the projector page open for this room right now? Grey ring = not open. */
function Dev({ name, p }: { name: string; p?: SurfacePresence }) {
  const on = (p?.online ?? 0) > 0;
  const title = on
    ? `${name} page is open${p!.online > 1 ? ` on ${p!.online} devices` : ""}`
    : p?.last_seen_ms
      ? `${name} page is closed. Last seen ${clock(p.last_seen_ms)}.`
      : `${name} page hasn't been opened yet.`;
  return (
    <span className={`dev${on ? " on" : ""}`} title={title}>
      <span className={`dot ${on ? "ok" : "off"}`} />
      {name}
      {on && p!.online > 1 ? ` ×${p!.online}` : ""}
    </span>
  );
}

/** Add a room, or edit one. Same fields, same layout (Room, Duration, Test label, Doc link). */
function RoomSheet({ room, onDone, onClose }: { room?: Snapshot; onDone: (s: Snapshot) => void; onClose: () => void }) {
  const editing = !!room;
  const locked = !!room && started(room);
  const [name, setName] = useState(room?.room_name ?? "");
  const [m, setM] = useState(String(room ? mins(room) : 180));
  const [test, setTest] = useState(room?.test_name ?? "");
  const [doc, setDoc] = useState(room?.doc_url ?? "");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => ref.current?.focus(), []);

  async function submit() {
    setBusy(true);
    setErr("");
    try {
      if (!editing) {
        onDone((await post<Snapshot>("/api/staff/rooms", { name, duration_min: Number(m), test_name: test.trim() || undefined, doc_url: doc.trim() || undefined }))!);
      } else {
        const body: Record<string, unknown> = {};
        if (name.trim() !== room!.room_name) body.name = name;
        if (test.trim() && test.trim() !== room!.test_name) body.test_name = test.trim();
        if (doc.trim() !== (room!.doc_url ?? "")) body.doc_url = doc.trim();
        if (!locked && Number(m) !== mins(room!)) body.duration_min = Number(m);
        onDone(Object.keys(body).length ? (await patch<Snapshot>(`/api/staff/rooms/${room!.room_id}`, body))! : room!);
      }
    } catch (x) {
      setErr(why(x));
      setBusy(false);
    }
  }

  return (
    <Sheet title={editing ? `Edit ${room!.room_name}` : "Add room"} onClose={onClose} onSubmit={submit}>
      <label>
        Room
        <input ref={ref} value={name} maxLength={60} onChange={(e) => setName(e.target.value)} placeholder="Evans 10" />
      </label>
      <label>
        Duration (minutes)
        <input type="number" inputMode="numeric" min={1} max={720} value={m} disabled={locked} onChange={(e) => setM(e.target.value)} />
        {locked && <small>Already started. Use +5 min to change the time.</small>}
      </label>
      <label>
        Test label (optional)
        <input value={test} maxLength={60} onChange={(e) => setTest(e.target.value)} placeholder="Individual Round" />
      </label>
      <label>
        Clarifications doc link (optional)
        <input type="url" value={doc} maxLength={500} onChange={(e) => setDoc(e.target.value)} placeholder="https://docs.google.com/…" />
      </label>
      <p className="error" role="alert" hidden={!err}>
        {err}
      </p>
      <div className="row">
        <button type="button" onClick={onClose}>
          Cancel
        </button>
        <button className="primary" disabled={busy || !name.trim() || !(Number(m) >= 1)}>
          {editing ? "Save" : "Add room"}
        </button>
      </div>
    </Sheet>
  );
}

/** Bulk edit: blank fields are left unchanged. Duration is skipped for rooms that already started. */
function BulkEdit({ rooms, onApply, onClose }: { rooms: Snapshot[]; onApply: (m: number | undefined, t: string | undefined) => void; onClose: () => void }) {
  const [m, setM] = useState("");
  const [t, setT] = useState("");
  const locked = rooms.filter(started).length;
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => ref.current?.focus(), []);
  const ok = (m.trim() !== "" && Number(m) >= 1 && Number(m) <= 720) || t.trim() !== "";
  return (
    <Sheet title={`Edit ${rooms.length} rooms`} onClose={onClose} onSubmit={() => onApply(m.trim() ? Number(m) : undefined, t.trim() || undefined)}>
      <p className="muted">Leave a field blank to keep each room&apos;s current value.</p>
      <label>
        Duration (minutes)
        <input ref={ref} type="number" inputMode="numeric" min={1} max={720} value={m} onChange={(e) => setM(e.target.value)} placeholder="unchanged" />
        {locked > 0 && <small>{locked} already started: their duration won&apos;t change.</small>}
      </label>
      <label>
        Test label
        <input value={t} maxLength={60} onChange={(e) => setT(e.target.value)} placeholder="unchanged" />
      </label>
      <div className="row">
        <button type="button" onClick={onClose}>
          Cancel
        </button>
        <button className="primary" disabled={!ok}>
          Apply to {rooms.length}
        </button>
      </div>
    </Sheet>
  );
}

/** Deleting hides rooms (they can be restored) but signs everyone in them out, so you type DELETE. */
function DeleteSheet({ rooms, onConfirm, onClose }: { rooms: Snapshot[]; onConfirm: (rooms: Snapshot[]) => void; onClose: () => void }) {
  const [typed, setTyped] = useState("");
  const ok = rooms.filter((r) => !inProgress(r));
  const busy = rooms.filter(inProgress);
  const list = (rs: Snapshot[]) => rs.slice(0, 4).map((r) => r.room_name).join(", ") + (rs.length > 4 ? ` and ${rs.length - 4} more` : "");
  return (
    <Sheet title={ok.length === 1 ? `Delete ${ok[0].room_name}?` : `Delete ${ok.length} rooms?`} onClose={onClose} onSubmit={() => onConfirm(ok)}>
      {ok.length > 0 ? (
        <p className="muted">
          {list(ok)}. They disappear for proctors and projectors, and anyone signed in to them is signed out. You can restore them later from &ldquo;Deleted&rdquo;.
        </p>
      ) : (
        <p className="muted">None of these can be deleted right now.</p>
      )}
      {busy.length > 0 && <p className="muted">Not deleted, timer in progress: {list(busy)}. Finish or reset them first.</p>}
      {ok.length > 0 && (
        <label>
          Type DELETE to confirm
          <input autoFocus value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
        </label>
      )}
      <div className="row">
        <button type="button" onClick={onClose}>
          Cancel
        </button>
        <button className="danger" disabled={typed !== "DELETE" || ok.length === 0}>
          Delete {ok.length === 1 ? "room" : "rooms"}
        </button>
      </div>
    </Sheet>
  );
}

export function Admin() {
  usePageTitle("Timers");
  useClock();
  useTick();
  const { data, setData, online, unauthorized } = useLive<Rooms>("/api/staff/rooms", "/api/staff/stream", mergeRooms, 2000, { presence: mergePresence, room_removed: dropRoom });
  const [err, setErr] = useState("");
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Snapshot | null>(null);
  const [bulkEditing, setBulkEditing] = useState(false);
  const [deleting, setDeleting] = useState<Snapshot[] | null>(null);
  const [showDeleted, setShowDeleted] = useState(false);
  const [emptying, setEmptying] = useState<Snapshot | null>(null);
  const [fresh, setFresh] = useState("");
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [filters, setFilters] = useState<Filters>(NO_FILTER);
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const [working, setWorking] = useState(false);
  useEffect(() => {
    if (unauthorized) go("/login");
  }, [unauthorized]);
  if (!data) return <main className="center" />;

  const pres = new Map((data.presence ?? []).map((p) => [p.room_id, p]));
  const everyone = data.rooms;
  const rooms = everyone.filter((r) => !r.deleted);
  const gone = everyone.filter((r) => r.deleted);
  const out = rooms.reduce((n, r) => n + r.students_out, 0);
  const count = (st: string) => rooms.filter((r) => r.timer.status === st).length;

  const matches = (r: Snapshot, f: Filters) => {
    const q = f.room.trim().toLowerCase();
    const p = pres.get(r.room_id);
    const ctl = (p?.control.online ?? 0) > 0;
    const dsp = (p?.display.online ?? 0) > 0;
    return (
      (!q || r.room_name.toLowerCase().includes(q)) &&
      (!f.test || r.test_name === f.test) &&
      (!f.status || r.timer.status === f.status) &&
      (!f.dur || String(mins(r)) === f.dur) &&
      (!f.dev || (f.dev === "no-proctor" && !ctl) || (f.dev === "no-display" && !dsp) || (f.dev === "none" && !ctl && !dsp))
    );
  };
  const shown = rooms.filter((r) => matches(r, filters));
  const shownGone = showDeleted ? gone.filter((r) => matches({ ...r, test_name: filters.test || r.test_name }, { ...filters, status: "", dur: "", dev: "" })) : [];
  const filtering = Object.values(filters).some(Boolean);
  const tests = [...new Set(rooms.map((r) => r.test_name))].sort();
  const durs = [...new Set(rooms.map(mins))].sort((a, b) => a - b);
  // Actions only ever touch rooms you can see AND have ticked.
  const chosen = shown.filter((r) => sel.has(r.room_id));
  const put = (snap: Snapshot) =>
    setData((d) => {
      if (!d) return d;
      const has = d.rooms.some((x) => x.room_id === snap.room_id);
      return { ...d, rooms: has ? d.rooms.map((x) => (x.room_id === snap.room_id ? snap : x)) : [...d.rooms, snap] };
    });

  /** Changing a filter drops ticks on rooms that would no longer be visible. */
  function setFilter(next: Filters) {
    const vis = new Set(rooms.filter((r) => matches(r, next)).map((r) => r.room_id));
    setSel((cur) => new Set([...cur].filter((id) => vis.has(id))));
    setFilters(next);
  }

  /** Ask first, unless Shift is held (wireframe: Shift-click skips the confirmation). */
  const ask = (e: React.MouseEvent, c: Confirm) => (e.shiftKey ? c.run() : setConfirm(c));

  /** Send a room's commands in order; stop at the first failure or rejection. Returns an error or "". */
  async function runRoom(s: Snapshot, kinds: Kind[]): Promise<string> {
    for (const k of kinds) {
      try {
        if (k === "reset") {
          put((s = (await post<Snapshot>(`/api/staff/rooms/${s.room_id}/reset`, { session_id: s.session_id }))!));
          continue;
        }
        const r = await sendCommand(k, s, k === "adjust" ? { delta_ms: 300_000 } : {});
        put(r.snapshot);
        s = r.snapshot;
        if (r.outcome === "rejected") return `${s.room_name}: not applied (${r.reason?.replaceAll("_", " ")})`;
      } catch {
        return `${s.room_name}: couldn't reach the server`;
      }
    }
    return "";
  }

  /** Run one room-level request (reset, restore, delete) and show a plain error if it fails. */
  async function call(fn: () => Promise<Snapshot | null>) {
    setErr("");
    try {
      const snap = await fn();
      if (snap) put(snap);
    } catch (e) {
      setErr(why(e));
    }
  }
  const act = async (s: Snapshot, kinds: Kind[]) => setErr(await runRoom(s, kinds));
  const reset = (s: Snapshot) => call(() => post<Snapshot>(`/api/staff/rooms/${s.room_id}/reset`, { session_id: s.session_id }));
  /** Empty = wipe a deleted room from the database for good. */
  const empty = async (s: Snapshot) => {
    setEmptying(null);
    setErr("");
    try {
      await post(`/api/staff/rooms/${s.room_id}/empty`);
      setData((d) => (d ? { ...d, rooms: d.rooms.filter((x) => x.room_id !== s.room_id) } : d));
    } catch (e) {
      setErr(why(e));
    }
  };
  const restore = (s: Snapshot) => call(() => post<Snapshot>(`/api/staff/rooms/${s.room_id}/restore`));

  async function finish(job: Promise<{ done: Snapshot[]; fails: string[] }>) {
    setWorking(true);
    setErr("");
    const { done, fails } = await job;
    setSel((cur) => new Set([...cur].filter((id) => !done.some((d) => d.room_id === id))));
    if (fails.length) setErr(`${done.length} done, ${fails.length} failed. ${fails.slice(0, 3).join("; ")}${fails.length > 3 ? "…" : ""}`);
    setWorking(false);
  }

  const bulk = (action: Action) => finish(pool(chosen.filter((s) => plan(action, s).length), (s) => runRoom(s, plan(action, s))));

  async function bulkEdit(m: number | undefined, t: string | undefined) {
    setBulkEditing(false);
    await finish(
      pool(chosen, async (s) => {
        const body: { duration_min?: number; test_name?: string } = {};
        if (m !== undefined && !started(s)) body.duration_min = m;
        if (t !== undefined) body.test_name = t;
        if (!Object.keys(body).length) return "";
        try {
          put((await patch<Snapshot>(`/api/staff/rooms/${s.room_id}`, body))!);
          return "";
        } catch (e) {
          return `${s.room_name}: ${why(e)}`;
        }
      }),
    );
  }

  async function remove(rs: Snapshot[]) {
    setDeleting(null);
    await finish(
      pool(rs, async (s) => {
        try {
          put((await del<Snapshot>(`/api/staff/rooms/${s.room_id}`))!);
          return "";
        } catch (e) {
          return `${s.room_name}: ${why(e)}`;
        }
      }),
    );
  }

  const TEXT: Record<Action, [string, string]> = {
    permit: ["Allow start for", "Proctors will be able to press Start."],
    start: ["Start", "Students will see the clock run right away."],
    adjust: ["Add 5 minutes to", "Students will see the change right away."],
    pause: ["Pause", "Students will see the clock stop."],
    resume: ["Resume", "Students will see the clock run again."],
    reset: ["Reset", "Clocks go back to full time and rooms need Allow start again."],
  };
  const askBulk = (e: React.MouseEvent, action: Action) => {
    const n = chosen.filter((s) => plan(action, s).length).length;
    if (!n) return setErr("None of the selected rooms can do that right now.");
    const skipped = chosen.length - n;
    ask(e, {
      title: `${TEXT[action][0]} ${n} room${n === 1 ? "" : "s"}?`,
      detail: skipped ? `${skipped} selected room${skipped === 1 ? " is" : "s are"} skipped (not in the right state).` : TEXT[action][1],
      confirm: action === "permit" ? "Allow start" : action === "start" ? "Start" : action === "adjust" ? "Add 5 min" : TEXT[action][0],
      run: () => bulk(action),
    });
  };

  const allOn = shown.length > 0 && chosen.length === shown.length;
  const toggle = (id: string) =>
    setSel((cur) => {
      const n = new Set(cur);
      if (!n.delete(id)) n.add(id);
      return n;
    });

  /** The buttons for one row, by timer state. Same order everywhere: main action, +5 min, more. */
  function actions(s: Snapshot) {
    const st = s.timer.status;
    return (
      <span className="row" style={{ flexWrap: "nowrap" }}>
        {st === "NOT_PERMITTED" && <button onClick={() => act(s, ["permit"])}>Allow start</button>}
        {st === "PERMITTED" && (
          <button className="primary" onClick={() => act(s, ["start"])}>
            Start
          </button>
        )}
        {st === "RUNNING" && (
          <button
            onClick={(e) =>
              ask(e, { title: `Pause ${s.room_name}?`, detail: "Students will see the clock stop.", confirm: "Pause", run: () => act(s, ["pause"]) })
            }
          >
            Pause
          </button>
        )}
        {st === "PAUSED" && (
          <button className="primary" onClick={() => act(s, ["resume"])}>
            Resume
          </button>
        )}
        {(st === "PAUSED" || st === "ENDED") && (
          <button
            onClick={(e) =>
              ask(e, {
                title: `Reset ${s.room_name}?`,
                detail: `The clock goes back to ${mins(s)} minutes and the room needs Allow start again.`,
                confirm: "Reset",
                run: () => reset(s),
              })
            }
          >
            Reset
          </button>
        )}
        {st !== "ENDED" && (
          <button
            onClick={(e) =>
              ask(e, { title: `Add 5 minutes to ${s.room_name}?`, detail: "Students will see the change right away.", confirm: "Add 5 min", run: () => act(s, ["adjust"]) })
            }
          >
            +5 min
          </button>
        )}
        <button onClick={() => setEditing(s)}>Edit…</button>
        <button disabled={inProgress(s)} onClick={() => setDeleting([s])}>
          Delete…
        </button>
      </span>
    );
  }

  return (
    <main className="admin">
      <AdminBar
        active="timers"
        online={online}
        summary={`${rooms.length} rooms · ${count("RUNNING")} running · ${count("NOT_PERMITTED") + count("PERMITTED")} not started · ${count("ENDED")} finished · ${out} student${out === 1 ? "" : "s"} out`}
        deleted={{ count: gone.length, shown: showDeleted, toggle: () => setShowDeleted(!showDeleted) }}
      >
        <button className="primary" onClick={() => setAdding(true)}>
          Add room
        </button>
      </AdminBar>
      {chosen.length > 0 && (
        <div className="bulk" role="toolbar" aria-label="Selected rooms">
          <strong>{chosen.length} selected</strong>
          <button disabled={working} onClick={(e) => askBulk(e, "permit")}>
            Allow start
          </button>
          <button className="primary" disabled={working} onClick={(e) => askBulk(e, "start")}>
            Start
          </button>
          <button disabled={working} onClick={(e) => askBulk(e, "pause")}>
            Pause
          </button>
          <button className="primary" disabled={working} onClick={(e) => askBulk(e, "resume")}>
            Resume
          </button>
          <button disabled={working} onClick={(e) => askBulk(e, "reset")}>
            Reset
          </button>
          <button disabled={working} onClick={(e) => askBulk(e, "adjust")}>
            +5 min
          </button>
          <button disabled={working} onClick={() => setBulkEditing(true)}>
            Edit…
          </button>
          <button disabled={working} onClick={() => setDeleting(chosen)}>
            Delete…
          </button>
          {working && <span className="muted">Working…</span>}
        </div>
      )}
      <p className="error" role="alert" hidden={!err}>
        {err}
      </p>
      <div className="table">
        <div className="tr th">
          <input
            type="checkbox"
            aria-label={filtering ? "Select all shown rooms" : "Select all rooms"}
            checked={allOn}
            ref={(el) => {
              if (el) el.indeterminate = chosen.length > 0 && !allOn;
            }}
            onChange={() => setSel(allOn ? new Set() : new Set(shown.map((r) => r.room_id)))}
          />
          <span>Room</span>
          <span>Test</span>
          <span>Status</span>
          <span>Remaining</span>
          <span>Duration</span>
          <span>Out</span>
          <span>Pages open</span>
          <span>Actions</span>
        </div>
        <div className="tr filters" role="search">
          <span />
          <input type="search" aria-label="Filter by room" placeholder="Filter rooms…" value={filters.room} onChange={(e) => setFilter({ ...filters, room: e.target.value })} />
          <select aria-label="Filter by test" value={filters.test} onChange={(e) => setFilter({ ...filters, test: e.target.value })}>
            <option value="">All</option>
            {tests.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
          <select aria-label="Filter by status" value={filters.status} onChange={(e) => setFilter({ ...filters, status: e.target.value })}>
            <option value="">All</option>
            {STATUSES.map((st) => (
              <option key={st} value={st}>
                {label({ timer: { status: st } } as Snapshot)}
              </option>
            ))}
          </select>
          <span className="muted">{filtering ? `${shown.length} of ${rooms.length}` : ""}</span>
          <select aria-label="Filter by duration" value={filters.dur} onChange={(e) => setFilter({ ...filters, dur: e.target.value })}>
            <option value="">All</option>
            {durs.map((d) => (
              <option key={d} value={d}>
                {d}m
              </option>
            ))}
          </select>
          <span />
          <select aria-label="Filter by pages open" value={filters.dev} onChange={(e) => setFilter({ ...filters, dev: e.target.value })}>
            <option value="">All</option>
            <option value="no-proctor">No proctor page</option>
            <option value="no-display">No projector page</option>
            <option value="none">Neither open</option>
          </select>
          <span>{filtering && <button onClick={() => setFilter(NO_FILTER)}>Clear filters</button>}</span>
        </div>
        {shown.length === 0 && shownGone.length === 0 && <p className="muted empty">{rooms.length === 0 ? "No rooms yet. Add one to get started." : "No rooms match these filters."}</p>}
        {shown.map((s) => {
          const st = s.timer.status;
          const p = pres.get(s.room_id);
          return (
            <div className={`tr${s.room_id === fresh ? " fresh" : ""}`} key={s.room_id}>
              <input type="checkbox" aria-label={`Select ${s.room_name}`} checked={sel.has(s.room_id)} onChange={() => toggle(s.room_id)} />
              <span>{s.room_name}</span>
              <span className="muted">{s.test_name}</span>
              <span className="pill" data-s={st}>
                {label(s)}
              </span>
              <span className="mono">{fmt(st === "ENDED" ? 0 : remainingMs(s, serverNow()))}</span>
              <span className="mono">{mins(s)}m</span>
              <span className="mono">{s.students_out || "–"}</span>
              <span className="devs">
                <Dev name="Proctor" p={p?.control} />
                <Dev name="Display" p={p?.display} />
              </span>
              {actions(s)}
            </div>
          );
        })}
        {shownGone.map((s) => (
          <div className="tr gone" key={s.room_id}>
            <span />
            <span>{s.room_name}</span>
            <span className="muted">{s.test_name}</span>
            <span className="muted">Deleted</span>
            <span />
            <span />
            <span />
            <span />
            <span className="row">
              <button onClick={() => restore(s)}>Restore</button>
              <button className="bad" onClick={() => setEmptying(s)}>
                Empty…
              </button>
            </span>
          </div>
        ))}
      </div>
      {confirm && (
        <Sheet title={confirm.title} onClose={() => setConfirm(null)}>
          <p className="muted">{confirm.detail} Tip: hold Shift to skip this question.</p>
          <div className="row">
            <button onClick={() => setConfirm(null)}>Cancel</button>
            <button
              className="primary"
              autoFocus
              onClick={() => {
                const run = confirm.run;
                setConfirm(null);
                run();
              }}
            >
              {confirm.confirm}
            </button>
          </div>
        </Sheet>
      )}
      {emptying && (
        <Sheet title={`Empty ${emptying.room_name}?`} onClose={() => setEmptying(null)}>
          <p className="muted">This wipes the room and its timer history from the database for good. You can&apos;t undo this. Use Restore if you might need it.</p>
          <div className="row end">
            <button onClick={() => setEmptying(null)}>Cancel</button>
            <button className="danger" onClick={() => empty(emptying)}>
              Empty
            </button>
          </div>
        </Sheet>
      )}
      {bulkEditing && <BulkEdit rooms={chosen} onApply={bulkEdit} onClose={() => setBulkEditing(false)} />}
      {deleting && <DeleteSheet rooms={deleting} onConfirm={remove} onClose={() => setDeleting(null)} />}
      {(adding || editing) && (
        <RoomSheet
          key={editing?.room_id ?? "new"}
          room={editing ?? undefined}
          onClose={() => {
            setAdding(false);
            setEditing(null);
          }}
          onDone={(snap) => {
            put(snap);
            if (adding) setFresh(snap.room_id);
            setAdding(false);
            setEditing(null);
          }}
        />
      )}
    </main>
  );
}
