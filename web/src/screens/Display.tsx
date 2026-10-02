import { useEffect, useState } from "react";
import { api, fmt, remainingMs, serverNow, type Snapshot } from "../api";
import { mergeRoom, useClock, useLive, useTick } from "../hooks";
import { go } from "../main";
import { FitText, useActive, useZoom, ZoomButtons } from "../components/FitText";
import { Dot } from "../components/ui";
import { FitList } from "../components/ClarList";

export function Display() {
  useClock();
  useTick();
  const [roomId, setRoomId] = useState<string | null>(null);
  const [needLogin, setNeedLogin] = useState(false);

  useEffect(() => {
    api<{ room_id: string }>("/api/me?surface=display")
      .then((m) => setRoomId(m!.room_id))
      .catch(async () => {
        // No display cookie yet: borrow the room from this laptop's control login if any.
        const c = await api<{ room_id: string }>("/api/me?surface=control").catch(() => null);
        go(`/login?surface=display${c ? `&room=${c.room_id}` : ""}`);
        setNeedLogin(true);
      });
  }, []);

  if (needLogin || !roomId) return <main className="center" />;
  return <Screen roomId={roomId} />;
}

function Screen({ roomId }: { roomId: string }) {
  const { data: s, online, unauthorized } = useLive<Snapshot>(`/api/rooms/${roomId}/snapshot`, `/api/rooms/${roomId}/stream?surface=display`, mergeRoom);
  useEffect(() => {
    if (unauthorized) go(`/login?surface=display&room=${roomId}`);
  }, [unauthorized, roomId]);
  if (!s) return <main className="center" />;

  return <View s={s} online={online} />;
}

/** Projector view (wireframe: Proctor · Display). Light theme, timer always fits the screen. */
function View({ s, online }: { s: Snapshot; online: boolean }) {
  const z = useZoom("display");
  const active = useActive();
  const ms = s.timer.status === "ENDED" ? 0 : remainingMs(s, serverNow());
  const tone = s.timer.status === "RUNNING" && ms <= 300_000 ? (ms === 0 ? "done" : "warn") : "";
  const showClars = s.timer.status !== "ENDED" && s.clarifications.length > 0; // hidden once time is up (swire)
  return (
    <main className={`display ${showClars ? "has-clars" : ""}`}>
      <header>
        <span className="where">
          {s.room_name} · {s.test_name}
        </span>
        <span className={`ctl ${active ? "" : "hide"}`}>
          <ZoomButtons z={z} />
        </span>
        <Dot online={online} />
      </header>
      <FitText className={`clock ${tone}`} text={fmt(ms)} zoom={z.zoom} />
      {showClars && <FitList items={s.clarifications} />}
      <footer>{label(s)}</footer>
    </main>
  );
}

export function label(s: Snapshot): string {
  return { NOT_PERMITTED: "Not started", PERMITTED: "Ready", RUNNING: "Running", PAUSED: "Paused", ENDED: "Finished" }[s.timer.status];
}
