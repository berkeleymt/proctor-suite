import { useEffect, useRef, useState } from "react";
import { fmt, post, remainingMs, sendCommand, serverNow, type Snapshot } from "../api";
import { useClock, usePoll, useTick } from "../hooks";
import { go } from "../main";
import { label } from "./Display";

type Rooms = { rooms: Snapshot[]; version?: number };

function AddRoom({ onDone, onClose }: { onDone: (s: Snapshot) => void; onClose: () => void }) {
  const [name, setName] = useState("");
  const [mins, setMins] = useState("180");
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
      onDone((await post<Snapshot>("/api/staff/rooms", { name, duration_min: Number(mins) }))!);
    } catch (x) {
      setErr(x instanceof Error ? x.message : "Couldn't reach the server.");
      setBusy(false);
    }
  }

  return (
    <div className="scrim" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <form className="sheet stack" onSubmit={submit}>
        <h2>Add room</h2>
        <label>
          Room
          <input ref={ref} value={name} maxLength={60} onChange={(e) => setName(e.target.value)} placeholder="Evans 10" />
        </label>
        <label>
          Duration (minutes)
          <input type="number" inputMode="numeric" min={1} max={720} value={mins} onChange={(e) => setMins(e.target.value)} />
        </label>
        <p className="error" role="alert" hidden={!err}>{err}</p>
        <div className="row">
          <button type="button" onClick={onClose}>Cancel</button>
          <button className="primary" disabled={busy || !name.trim() || !(Number(mins) >= 1)}>Add room</button>
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
              <span className="row">
                {st === "NOT_PERMITTED" && <button onClick={() => act(s, "permit")}>Allow start</button>}
                {st === "PERMITTED" && (
                  <button className="primary" onClick={() => act(s, "start")}>
                    Start
                  </button>
                )}
                {st !== "ENDED" && <button onClick={() => act(s, "adjust")}>+5 min</button>}
              </span>
            </div>
          );
        })}
      </div>
      {adding && (
        <AddRoom
          onClose={() => setAdding(false)}
          onDone={(snap) => {
            const rooms = [...data!.rooms.filter((x) => x.room_id !== snap.room_id), snap];
            setData({ ...data!, rooms: rooms.sort((a, b) => a.room_name.localeCompare(b.room_name)) });
            setFresh(snap.room_id);
            setAdding(false);
          }}
        />
      )}
    </main>
  );
}
