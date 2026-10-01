import { useEffect, useState } from "react";
import { api, fmt, remainingMs, serverNow, type Snapshot } from "../api";
import { useClock, usePoll, useTick } from "../hooks";
import { go } from "../main";

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
  const { data: s, online, unauthorized } = usePoll<Snapshot>(`/api/rooms/${roomId}/snapshot`);
  useEffect(() => {
    if (unauthorized) go(`/login?surface=display&room=${roomId}`);
  }, [unauthorized, roomId]);
  if (!s) return <main className="center" />;

  const ms = s.timer.status === "ENDED" ? 0 : remainingMs(s, serverNow());
  const tone = s.timer.status === "RUNNING" && ms <= 300_000 ? (ms === 0 ? "done" : "warn") : "";
  return (
    <main className="display">
      <header>
        <span>
          {s.room_name} · {s.test_name}
        </span>
        <span className={`dot ${online ? "ok" : "bad"}`} title={online ? "Connected" : "Offline"} />
      </header>
      <div className={`clock ${tone}`} aria-live="off">
        {fmt(ms)}
      </div>
      <footer>{label(s)}</footer>
    </main>
  );
}

export function label(s: Snapshot): string {
  return { NOT_PERMITTED: "Not started", PERMITTED: "Ready", RUNNING: "Running", PAUSED: "Paused", ENDED: "Finished" }[s.timer.status];
}
