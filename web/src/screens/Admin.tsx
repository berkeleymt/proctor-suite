import { useEffect, useRef, useState } from "react";
import { ApiError, fmt, patch, post, remainingMs, sendCommand, serverNow, type Snapshot } from "../api";
import { mergeRooms, useClock, useLive, useTick } from "../hooks";
import { go } from "../main";
import { label } from "./Display";

type Rooms = { rooms: Snapshot[]; version?: number };

function RoomSheet({ room, onDone, onClose }: { room?: Snapshot; onDone: (s: Snapshot) => void; onClose: () => void }) {
  const editing = !!room;
  const started = !!room && !["NOT_PERMITTED", "PERMITTED"].includes(room.timer.status);
  const [name, setName] = useState(room?.room_name ?? "");
  const [mins, setMins] = useState(String(room ? Math.round(room.timer.duration_ms / 60_000) : 180));
  const [test, setTest] = useState(room ? room.test_name : "");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => ref.current?.focus(), []);
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const dur = Number(mins);
      onDone(
        editing
          ? (await patch<Snapshot>(`/api/staff/rooms/${room!.room_id}`, {
              test_name: test.trim() || undefined,
              ...(started ? {} : { duration_min: dur }),
            }))!
          : (await post<Snapshot>("/api/staff/rooms", { name, duration_min: dur, test_name: test.trim() || undefined }))!,
      );
    } catch (x) {
      setErr(x instanceof Error ? x.message : "Couldn't reach the server.");
      setBusy(false);
    }
  }

  return (
    <div className="scrim" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <form className="sheet stack" onSubmit={submit}>
        <h2>{editing ? `Edit ${room!.room_name}` : "Add room"}</h2>
        {!editing && (
          <label>
            Room
            <input ref={ref} value={name} maxLength={60} onChange={(e) => setName(e.target.value)} placeholder="Evans 10" />
          </label>
        )}
        <label>
          Duration (minutes)
          <input type="number" inputMode="numeric" min={1} max={720} value={mins} disabled={started} onChange={(e) => setMins(e.target.value)} />
          {started && <small>Already started. Use +5 min to change the time.</small>}
        </label>
        <label>
          Test label (optional)
          <input value={test} maxLength={60} onChange={(e) => setTest(e.target.value)} placeholder="Individual Round" />
        </label>
        <p className="error" role="alert" hidden={!err}>{err}</p>
        <div className="row">
          <button type="button" onClick={onClose}>Cancel</button>
          <button className="primary" disabled={busy || !name.trim() || !(Number(mins) >= 1)}>{editing ? "Save" : "Add room"}</button>
        </div>
      </form>
    </div>
  );
}

type Kind = "permit" | "start" | "adjust";
type Action = "permit" | "start" | "adjust";
type Confirm = { title: string; detail: string; run: () => void };
type Filters = { room: string; test: string; status: string; dur: string };
const NO_FILTER: Filters = { room: "", test: "", status: "", dur: "" };
const STATUSES = ["NOT_PERMITTED", "PERMITTED", "RUNNING", "PAUSED", "ENDED"] as const;
const mins = (s: Snapshot) => Math.round(s.timer.duration_ms / 60_000);
const started = (s: Snapshot) => !["NOT_PERMITTED", "PERMITTED"].includes(s.timer.status);

/** What a bulk action would do to one room: the commands to send, or none (skipped). */
function plan(action: Action, s: Snapshot): Kind[] {
  const st = s.timer.status;
  if (action === "adjust") return st === "ENDED" ? [] : ["adjust"];
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

/** Bulk edit: blank fields are left unchanged. Duration is skipped for rooms that already started. */
function BulkEdit({ rooms, onApply, onClose }: { rooms: Snapshot[]; onApply: (m: number | undefined, t: string | undefined) => void; onClose: () => void }) {
  const [m, setM] = useState("");
  const [t, setT] = useState("");
  const locked = rooms.filter(started).length;
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => ref.current?.focus(), []);
  const ok = (m.trim() !== "" && Number(m) >= 1 && Number(m) <= 720) || t.trim() !== "";
  return (
    <div className="scrim" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <form
        className="sheet stack"
        onSubmit={(e) => {
          e.preventDefault();
          onApply(m.trim() ? Number(m) : undefined, t.trim() || undefined);
        }}
      >
        <h2>Edit {rooms.length} rooms</h2>
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
      </form>
    </div>
  );
}

export function Admin() {
  useClock();
  useTick();
  const { data, setData, online, unauthorized } = useLive<Rooms>("/api/staff/rooms", "/api/staff/stream", mergeRooms);
  const [err, setErr] = useState("");
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Snapshot | null>(null);
  const [bulkEditing, setBulkEditing] = useState(false);
  const [fresh, setFresh] = useState("");
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [filters, setFilters] = useState<Filters>(NO_FILTER);
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const [working, setWorking] = useState(false);
  useEffect(() => {
    if (unauthorized) go("/login");
  }, [unauthorized]);
  if (!data) return <main className="center" />;

  const rooms = data.rooms;
  const count = (st: string) => rooms.filter((r) => r.timer.status === st).length;
  const q = filters.room.trim().toLowerCase();
  const shown = rooms.filter(
    (r) =>
      (!q || r.room_name.toLowerCase().includes(q)) &&
      (!filters.test || r.test_name === filters.test) &&
      (!filters.status || r.timer.status === filters.status) &&
      (!filters.dur || String(mins(r)) === filters.dur),
  );
  const filtering = shown.length !== rooms.length || Object.values(filters).some(Boolean);
  const tests = [...new Set(rooms.map((r) => r.test_name))].sort();
  const durs = [...new Set(rooms.map(mins))].sort((a, b) => a - b);
  // Actions only ever touch rooms you can see AND have ticked.
  const chosen = shown.filter((r) => sel.has(r.room_id));
  const put = (snap: Snapshot) =>
    setData((d) => (d ? { ...d, rooms: d.rooms.map((x) => (x.room_id === snap.room_id ? snap : x)) } : d));

  /** Changing a filter drops ticks on rooms that would no longer be visible. */
  function setFilter(next: Filters) {
    const nq = next.room.trim().toLowerCase();
    const vis = new Set(
      rooms
        .filter(
          (r) =>
            (!nq || r.room_name.toLowerCase().includes(nq)) &&
            (!next.test || r.test_name === next.test) &&
            (!next.status || r.timer.status === next.status) &&
            (!next.dur || String(mins(r)) === next.dur),
        )
        .map((r) => r.room_id),
    );
    setSel((cur) => new Set([...cur].filter((id) => vis.has(id))));
    setFilters(next);
  }

  /** Ask first, unless Shift is held (wireframe: Shift-click skips the confirmation). */
  const ask = (e: React.MouseEvent, c: Confirm) => (e.shiftKey ? c.run() : setConfirm(c));

  /** Send a room's commands in order; stop at the first failure or rejection. Returns an error or "". */
  async function runRoom(s: Snapshot, kinds: Kind[]): Promise<string> {
    for (const k of kinds) {
      try {
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

  async function act(s: Snapshot, kinds: Kind[]) {
    setErr(await runRoom(s, kinds));
  }

  async function finish(job: Promise<{ done: Snapshot[]; fails: string[] }>) {
    setWorking(true);
    setErr("");
    const { done, fails } = await job;
    setSel((cur) => new Set([...cur].filter((id) => !done.some((d) => d.room_id === id))));
    if (fails.length) setErr(`${done.length} done, ${fails.length} failed. ${fails.slice(0, 3).join("; ")}${fails.length > 3 ? "…" : ""}`);
    setWorking(false);
  }

  const bulk = (action: Action) =>
    finish(pool(chosen.filter((s) => plan(action, s).length), (s) => runRoom(s, plan(action, s))));

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
          return `${s.room_name}: ${e instanceof ApiError ? e.message : "couldn't reach the server"}`;
        }
      }),
    );
  }

  const TEXT: Record<Action, [string, string]> = {
    permit: ["Allow start for", "Proctors will be able to press Start."],
    start: ["Start", "Students will see the clock run right away."],
    adjust: ["Add 5 minutes to", "Students will see the change right away."],
  };
  const askBulk = (e: React.MouseEvent, action: Action) => {
    const n = chosen.filter((s) => plan(action, s).length).length;
    if (!n) return setErr("None of the selected rooms can do that right now.");
    const skipped = chosen.length - n;
    ask(e, {
      title: `${TEXT[action][0]} ${n} room${n === 1 ? "" : "s"}?`,
      detail: skipped ? `${skipped} selected room${skipped === 1 ? " is" : "s are"} skipped (not in the right state).` : TEXT[action][1],
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

  return (
    <main className="admin">
      <header className="bar">
        <h1>Timers</h1>
        <span className="muted">
          {rooms.length} rooms · {count("RUNNING")} running · {count("NOT_PERMITTED") + count("PERMITTED")} not started ·{" "}
          {count("ENDED")} finished
        </span>
        <span className={`dot ${online ? "ok" : "bad"}`} />
        <button className="primary" onClick={() => setAdding(true)}>
          Add room
        </button>
        <button
          onClick={async () => {
            await post("/api/auth/logout?surface=staff").catch(() => {});
            go("/login");
          }}
        >
          Log out
        </button>
      </header>
      {chosen.length > 0 && (
        <div className="bulk" role="toolbar" aria-label="Selected rooms">
          <strong>{chosen.length} selected</strong>
          <button disabled={working} onClick={(e) => askBulk(e, "permit")}>
            Allow start
          </button>
          <button className="primary" disabled={working} onClick={(e) => askBulk(e, "start")}>
            Start
          </button>
          <button disabled={working} onClick={(e) => askBulk(e, "adjust")}>
            +5 min
          </button>
          <button disabled={working} onClick={() => setBulkEditing(true)}>
            Edit…
          </button>
          <button disabled={working} onClick={() => setSel(new Set())}>
            Clear
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
          <span>{filtering && <button onClick={() => setFilter(NO_FILTER)}>Clear filters</button>}</span>
        </div>
        {shown.length === 0 && <p className="muted empty">No rooms match these filters.</p>}
        {shown.map((s) => {
          const st = s.timer.status;
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
              <span className="row">
                {st === "NOT_PERMITTED" && <button onClick={() => act(s, ["permit"])}>Allow start</button>}
                {st === "PERMITTED" && (
                  <button className="primary" onClick={() => act(s, ["start"])}>
                    Start
                  </button>
                )}
                {st !== "ENDED" && (
                  <button
                    onClick={(e) =>
                      ask(e, {
                        title: `Add 5 minutes to ${s.room_name}?`,
                        detail: "Students will see the change right away.",
                        run: () => act(s, ["adjust"]),
                      })
                    }
                  >
                    +5 min
                  </button>
                )}
                <button onClick={() => setEditing(s)}>Edit…</button>
              </span>
            </div>
          );
        })}
      </div>
      {confirm && (
        <div className="scrim" onClick={(e) => e.target === e.currentTarget && setConfirm(null)}>
          <div className="sheet stack" role="alertdialog" aria-label={confirm.title}>
            <h2>{confirm.title}</h2>
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
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
      {bulkEditing && <BulkEdit rooms={chosen} onApply={bulkEdit} onClose={() => setBulkEditing(false)} />}
      {(adding || editing) && (
        <RoomSheet
          key={editing?.room_id ?? "new"}
          room={editing ?? undefined}
          onClose={() => {
            setAdding(false);
            setEditing(null);
          }}
          onDone={(snap) => {
            const rooms = [...data.rooms.filter((x) => x.room_id !== snap.room_id), snap];
            setData({ ...data, rooms: rooms.sort((a, b) => a.room_name.localeCompare(b.room_name)) });
            if (adding) setFresh(snap.room_id);
            setAdding(false);
            setEditing(null);
          }}
        />
      )}
    </main>
  );
}
