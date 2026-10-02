import { useEffect, useState } from "react";
import { api, ApiError, fmt, post, remainingMs, sendCommand, serverNow, type Snapshot } from "../api";
import { mergeRoom, useClock, useLive, useTick } from "../hooks";
import { go } from "../main";
import { label } from "./Display";
import { FitText, useZoom, ZoomButtons } from "../components/FitText";
import { Dot, Sheet } from "../components/ui";
import { usePageTitle } from "../brand";
import { DISPLAY_WINDOW } from "../fullscreen";
import { BathroomLog } from "../components/BathroomLog";

type Me = { room_id: string; room_name: string };

/** The projector window: as big as the screen this laptop is on; it then goes full screen itself. */
function openDisplay() {
  const s = window.screen as Screen & { availLeft?: number; availTop?: number };
  const at = `left=${s.availLeft ?? 0},top=${s.availTop ?? 0},width=${s.availWidth},height=${s.availHeight}`;
  window.open("/display", DISPLAY_WINDOW, `popup,${at}`);
}

export function Proctor() {
  usePageTitle("Proctor");
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
  const { data: s, setData, online, unauthorized } = useLive<Snapshot>(`/api/rooms/${roomId}/snapshot`, `/api/rooms/${roomId}/stream?surface=control`, mergeRoom);
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
        <Dot online={online} />
        <button onClick={logout}>Log out</button>
      </header>
      <div className="clock-wrap">
        <FitText className="clock" text={fmt(ms)} zoom={z.zoom} />
        <ZoomButtons z={z} />
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
        ) : st === "ENDED" ? (
          <button disabled>Time&apos;s up</button>
        ) : (
          <button className="primary" disabled={st !== "PERMITTED"} onClick={() => act("start")}>
            Start
          </button>
        )}
        <button onClick={openDisplay}>
          <span className="long">Open display window ↗</span>
          <span className="short">Display ↗</span>
        </button>
      </div>
      <p className="hint">
        {st === "NOT_PERMITTED"
          ? "Start unlocks when an admin allows it."
          : st === "PAUSED"
            ? "Paused. Resume when you're ready. Only an admin can reset the timer."
            : st === "ENDED"
              ? "The timer is finished. Only an admin can reset it."
              : "\u00a0"}
      </p>
      <BathroomLog s={s} setData={setData} />
      {asking && (
        <Sheet title={`Pause the timer for ${s.room_name}?`} onClose={() => setAsking(false)}>
          <p className="muted">Students will see the clock stop.</p>
          <div className="row">
            <button onClick={() => setAsking(false)}>Cancel</button>
            <button
              className="primary"
              autoFocus
              onClick={() => {
                setAsking(false);
                act("pause");
              }}
            >
              Pause
            </button>
          </div>
        </Sheet>
      )}
    </main>
  );
}
