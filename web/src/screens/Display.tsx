import { useEffect, useState } from "react";
import { api, fmt, remainingMs, serverNow, type Snapshot } from "../api";
import { mergeRoom, useClock, useLive, useTick } from "../hooks";
import { go } from "../main";
import { FitText } from "../components/FitText";
import { Dot } from "../components/ui";
import { usePageTitle } from "../brand";
import { isDisplayWindow, useAutoFullscreen } from "../fullscreen";
import { docEmbedUrl, FitList } from "../components/ClarList";
import { useDisplayValues } from "../displaySettings";

export function Display() {
  usePageTitle("Display");
  const waitingFs = useAutoFullscreen(isDisplayWindow());
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
  return (
    <>
      <Screen roomId={roomId} />
      {waitingFs && <p className="fs-hint">Click anywhere for full screen</p>}
    </>
  );
}

function Screen({ roomId }: { roomId: string }) {
  const { data: s, online, unauthorized } = useLive<Snapshot>(`/api/rooms/${roomId}/snapshot`, `/api/rooms/${roomId}/stream?surface=display`, mergeRoom);
  useEffect(() => {
    if (unauthorized) go(`/login?surface=display&room=${roomId}`);
  }, [unauthorized, roomId]);
  if (!s) return <main className="center" />;

  return <View s={s} online={online} />;
}

/**
 * Projector view (wireframe: Proctor · Display). Light theme, timer always fits the screen.
 * No buttons here: sizes are the room's, set on the proctor page (ADR 0019).
 */
export function View({ s, online }: { s: Snapshot; online: boolean }) {
  const size = useDisplayValues(s);
  const ms = s.timer.status === "ENDED" ? 0 : remainingMs(s, serverNow());
  const tone = s.timer.status === "RUNNING" && ms <= 300_000 ? (ms === 0 ? "done" : "warn") : "";
  const live = s.timer.status !== "ENDED"; // clarifications go away once time is up (swire)
  const doc = live && !!s.doc_url; // a doc link replaces the text list entirely (wireframe)
  const text = live && !s.doc_url && s.clarifications.length > 0;
  return (
    <main className={`display ${doc || text ? "has-clars" : ""}`}>
      <header>
        <span className="where">
          {s.room_name} · {s.test_name}
        </span>
        <Dot online={online} />
      </header>
      <FitText className={`clock ${tone}`} text={fmt(ms)} zoom={size.timer_zoom_pct / 100} />
      {text && <FitList items={s.clarifications} size={size.clar_size} />}
      {doc && <iframe className="doc" title="Clarifications document" src={docEmbedUrl(s.doc_url!)} referrerPolicy="no-referrer" sandbox="allow-scripts allow-same-origin allow-popups allow-forms" />}
      <footer>{label(s)}{!live && (s.clarifications.length > 0 || s.doc_url) ? `. ${CLARS_HIDDEN}` : ""}</footer>
    </main>
  );
}

/** Why the clarifications vanished: they only show until the timer ends (swire behavior). */
export const CLARS_HIDDEN = "Clarifications are hidden once time is up.";

export function label(s: Snapshot): string {
  return { NOT_PERMITTED: "Not started", PERMITTED: "Ready", RUNNING: "Running", PAUSED: "Paused", ENDED: "Finished" }[s.timer.status];
}
