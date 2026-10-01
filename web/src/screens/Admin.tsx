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

export function Admin() {
  useClock();
  useTick();
  const { data, setData, online, unauthorized } = usePoll<Rooms>("/api/staff/rooms");
  const [err, setErr] = useState("");
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Snapshot | null>(null);
  const [fresh, setFresh] = useState("");
  useEffect(() => {
    if (unauthorized) go("/login");
  }, [unauthorized]);
  if (!data) return <main className="center" />;

  const rooms = data.rooms;
  const count = (st: string) => rooms.filter((r) => r.timer.status === st).length;

  async function act(s: Snapshot, type: "permit" | "start" | "adjust") {
    setErr("");
    try {
      const r = await sendCommand(type, s, type === "adjust" ? { delta_ms: 300_000 } : {});
      setData({ ...data!, rooms: data!.rooms.map((x) => (x.room_id === s.room_id ? r.snapshot : x)) });
      if (r.outcome === "rejected") setErr(`${s.room_name}: not applied (${r.reason?.replaceAll("_", " ")})`);
    } catch {
      setErr(`${s.room_name}: couldn't reach the server. Try again.`);
    }
  }

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
      <p className="error" role="alert" hidden={!err}>
        {err}
      </p>
      <div className="table">
        <div className="tr th">
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
              <span>{s.room_name}</span>
              <span className="pill" data-s={st}>
                {label(s)}
              </span>
              <span className="mono">{fmt(st === "ENDED" ? 0 : remainingMs(s, serverNow()))}</span>
              <span className="mono">{Math.round(s.timer.duration_ms / 60_000)}m</span>
              <span className="row">
                {st === "NOT_PERMITTED" && <button onClick={() => act(s, "permit")}>Allow start</button>}
                {st === "PERMITTED" && (
                  <button className="primary" onClick={() => act(s, "start")}>
                    Start
                  </button>
                )}
                {st !== "ENDED" && <button onClick={() => act(s, "adjust")}>+5 min</button>}
                <button onClick={() => setEditing(s)}>Edit…</button>
              </span>
            </div>
          );
        })}
      </div>
      {(adding || editing) && (
        <RoomSheet
          key={editing?.room_id ?? "new"}
          room={editing ?? undefined}
          onClose={() => {
            setAdding(false);
            setEditing(null);
          }}
          onDone={(snap) => {
            const rooms = [...data!.rooms.filter((x) => x.room_id !== snap.room_id), snap];
            setData({ ...data!, rooms: rooms.sort((a, b) => a.room_name.localeCompare(b.room_name)) });
            if (adding) setFresh(snap.room_id);
            setAdding(false);
            setEditing(null);
          }}
        />
      )}
    </main>
  );
}
