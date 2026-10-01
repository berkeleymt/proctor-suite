import { useEffect, useState } from "react";
import { api, ApiError, fmt, post, remainingMs, sendCommand, serverNow, type Snapshot } from "../api";
import { useClock, usePoll, useTick } from "../hooks";
import { go } from "../main";
import { label } from "./Display";
import { FitText, useZoom, ZoomButtons } from "../components/FitText";

type Me = { room_id: string; room_name: string };

export function Proctor() {
  useClock();
  const [me, setMe] = useState<Me | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  useEffect(() => {
    api<Me>("/api/me?surface=control").then((m) => setMe(m!)).catch(() => go("/login"));
  }, []);
  if (!me) return <main className="center" />;
  const logout = async () => {
    await post("/api/auth/logout?surface=control").catch(() => {});
    go("/login");
  };
  // Wrong-room safeguard (protocol §3, ADR 0001): nothing is enabled until the room is confirmed.
  if (!confirmed)
    return (
      <main className="center">
        <div className="card stack center-text">
          <p className="muted">Is this your room?</p>
          <h1 className="huge">{me.room_name}</h1>
          <br></br>
          <button className="primary" onClick={() => setConfirmed(true)}>
            Yes, this is my room
          </button>
          <button onClick={logout}>No, sign out</button>
        </div>
      </main>
    );
  return <Panel roomId={me.room_id} logout={logout} />;
}

function Panel({ roomId, logout }: { roomId: string; logout: () => void }) {
  useTick();
  const { data: s, setData, online, unauthorized } = usePoll<Snapshot>(`/api/rooms/${roomId}/snapshot`);
  const [err, setErr] = useState("");
  const [asking, setAsking] = useState(false);
  const z = useZoom("proctor");
  useEffect(() => {
    if (unauthorized) go("/login");
  }, [unauthorized]);
  if (!s) return <main className="center" />;

  async function act(type: "start" | "pause" | "resume") {
    setErr("");
    try {
      const r = await sendCommand(type, s!);
      setData(r.snapshot);
      if (r.outcome === "rejected") setErr(`Not applied: ${r.reason?.replaceAll("_", " ")}`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "No connection. Try again.");
    }
  }

  const st = s.timer.status;
  const ms = st === "ENDED" ? 0 : remainingMs(s, serverNow());
  return (
    <main className="panel">
      <header className="bar">
        <div>
          <strong>{s.room_name}</strong> <span className="pill" data-s={st}>{label(s)}</span>
        </div>
        <span className={`dot ${online ? "ok" : "bad"}`} title={online ? "Connected" : "Offline"} />
        <button onClick={logout}>Log out</button>
      </header>
      <div className="clock-wrap">
        <FitText className="clock" text={fmt(ms)} zoom={z.zoom} />
        {/* <ZoomButtons z={z} /> */}
      </div>
      <p className="error" role="alert" hidden={!err}>
        {err}
      </p>
      <div className="row actions">
        {st === "RUNNING" ? (
          <button onClick={() => setAsking(true)}>Pause</button>
        ) : st === "PAUSED" ? (
          <button className="primary" onClick={() => act("resume")}>
            Resume
          </button>
        ) : (
          <button className="primary" disabled={st !== "PERMITTED"} onClick={() => act("start")} title={st === "NOT_PERMITTED" ? "Waiting for an admin to allow start" : undefined}>
            Start
          </button>
        )}
        <button onClick={() => window.open("/display", "proctor-display", "popup")}>
          <span className="long">Open display window ↗</span>
          <span className="short">Display ↗</span>
        </button>
      </div>
      {asking && (
        <div className="scrim" onClick={() => setAsking(false)}>
          <div className="sheet stack" role="dialog" aria-modal onClick={(e) => e.stopPropagation()}>
            <h2>Pause the timer for {s.room_name}?</h2>
            <p className="muted">Students will see the clock stop.</p>
            <button
              className="primary"
              onClick={() => {
                setAsking(false);
                act("pause");
              }}
            >
              Pause
            </button>
            <button onClick={() => setAsking(false)}>Cancel</button>
          </div>
        </div>
      )}
    </main>
  );
}
