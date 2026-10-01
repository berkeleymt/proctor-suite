import { useEffect, useRef, useState } from "react";
import { fmt, patch, post, remainingMs, sendCommand, serverNow, type Snapshot } from "../api";
import { useClock, usePoll, useTick } from "../hooks";
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
type Confirm = { title: string; detail: string; run: () => void };

/** What a bulk action would do to one room: the commands to send, or none (skipped). */
function plan(action: "start" | "adjust", s: Snapshot): Kind[] {
  const st = s.timer.status;
  if (action === "adjust") return st === "ENDED" ? [] : ["adjust"];
  return st === "NOT_PERMITTED" ? ["permit", "start"] : st === "PERMITTED" ? ["start"] : [];
}

export function Admin() {
  useClock();
  useTick();
  const { data, setData, online, unauthorized } = usePoll<Rooms>("/api/staff/rooms");
  const [err, setErr] = useState("");
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Snapshot | null>(null);
  const [fresh, setFresh] = useState("");
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const [working, setWorking] = useState(false);
  useEffect(() => {
    if (unauthorized) go("/login");
  }, [unauthorized]);
  if (!data) return <main className="center" />;

  const rooms = data.rooms;
  const count = (st: string) => rooms.filter((r) => r.timer.status === st).length;
  const chosen = rooms.filter((r) => sel.has(r.room_id));
  const put = (snap: Snapshot) =>
    setData((d) => (d ? { ...d, rooms: d.rooms.map((x) => (x.room_id === snap.room_id ? snap : x)) } : d));

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
    setErr("");
    setErr(await runRoom(s, kinds));
  }

  /** Bulk: a few rooms at a time so 50 rooms don't open 50 connections (invariant 2). */
  async function bulk(action: "start" | "adjust") {
    const todo = chosen.map((s) => ({ s, kinds: plan(action, s) })).filter((t) => t.kinds.length);
    setWorking(true);
    setErr("");
    const fails: string[] = [];
    const done: string[] = [];
    const queue = [...todo];
    await Promise.all(
      Array.from({ length: Math.min(6, queue.length) }, async () => {
        for (let t = queue.shift(); t; t = queue.shift()) {
          const e = await runRoom(t.s, t.kinds);
          if (e) fails.push(e);
          else done.push(t.s.room_id);
        }
      }),
    );
    setSel((cur) => new Set([...cur].filter((id) => !done.includes(id))));
    if (fails.length) setErr(`${done.length} done, ${fails.length} failed. ${fails.slice(0, 3).join("; ")}${fails.length > 3 ? "…" : ""}`);
    setWorking(false);
  }

  const askBulk = (e: React.MouseEvent, action: "start" | "adjust") => {
    const n = chosen.filter((s) => plan(action, s).length).length;
    if (!n) return setErr("None of the selected rooms can do that right now.");
    const skipped = chosen.length - n;
    ask(e, {
      title: action === "start" ? `Start ${n} room${n === 1 ? "" : "s"}?` : `Add 5 minutes to ${n} room${n === 1 ? "" : "s"}?`,
      detail: skipped ? `${skipped} selected room${skipped === 1 ? " is" : "s are"} skipped (already running or finished).` : "Students will see the change right away.",
      run: () => bulk(action),
    });
  };

  const allOn = rooms.length > 0 && chosen.length === rooms.length;
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
          <button className="primary" disabled={working} onClick={(e) => askBulk(e, "start")}>
            Start selected
          </button>
          <button disabled={working} onClick={(e) => askBulk(e, "adjust")}>
            +5 min selected
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
            aria-label="Select all rooms"
            checked={allOn}
            ref={(el) => {
              if (el) el.indeterminate = chosen.length > 0 && !allOn;
            }}
            onChange={() => setSel(allOn ? new Set() : new Set(rooms.map((r) => r.room_id)))}
          />
          <span>Room</span>
          <span>Status</span>
          <span>Remaining</span>
          <span>Duration</span>
          <span>Actions</span>
        </div>
        {rooms.map((s) => {
          const st = s.timer.status;
          return (
            <div className={`tr${s.room_id === fresh ? " fresh" : ""}`} key={s.room_id}>
              <input type="checkbox" aria-label={`Select ${s.room_name}`} checked={sel.has(s.room_id)} onChange={() => toggle(s.room_id)} />
              <span>{s.room_name}</span>
              <span className="pill" data-s={st}>
                {label(s)}
              </span>
              <span className="mono">{fmt(st === "ENDED" ? 0 : remainingMs(s, serverNow()))}</span>
              <span className="mono">{Math.round(s.timer.duration_ms / 60_000)}m</span>
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
