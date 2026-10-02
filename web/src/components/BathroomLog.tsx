import { useRef, useState } from "react";
import { ApiError, post, serverNow, type Snapshot } from "../api";

type Visit = Snapshot["bathroom_out"][number];

const clock = (ms: number) => new Date(ms).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
const minsAway = (v: Visit) => Math.max(0, Math.floor((serverNow() - v.left_ms) / 60_000));
const LATE_MIN = 10; // rows past this are highlighted (wireframe)

/** Proctor · Bathroom log (wireframe): type an ID, Mark out; Returned when they are back.
 *  The parent re-renders every second, so "out for" stays live without its own timer. */
export function BathroomLog({ s, setData }: { s: Snapshot; setData: (s: Snapshot) => void }) {
  const [student, setStudent] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  // One id per attempt, reused if the request has to be retried, so a slow network can never log
  // the same student twice (invariant 3). Typing something else starts a new attempt.
  const attempt = useRef<string | null>(null);
  const base = `/api/rooms/${s.room_id}/bathroom`;

  async function markOut(e: React.FormEvent) {
    e.preventDefault();
    const id = student.trim();
    if (!id || busy) return;
    setBusy(true);
    setErr("");
    attempt.current ??= crypto.randomUUID();
    try {
      setData((await post<Snapshot>(base, { id: attempt.current, student_id: id }))!);
      setStudent("");
      attempt.current = null;
    } catch (x) {
      if (x instanceof ApiError) attempt.current = null; // the server answered, so this attempt is over
      setErr(x instanceof ApiError ? x.message : "No connection. Press Mark out to try again.");
    } finally {
      setBusy(false);
    }
  }

  async function back(v: Visit) {
    setErr("");
    try {
      setData((await post<Snapshot>(`${base}/${v.id}/return`))!);
    } catch (x) {
      setErr(x instanceof ApiError ? x.message : "No connection. Press Returned to try again.");
    }
  }

  return (
    <section className="bath" aria-labelledby="bath-h">
      <h2 id="bath-h">Bathroom</h2>
      <form className="row bath-in" onSubmit={markOut}>
        <input
          value={student}
          onChange={(e) => {
            setStudent(e.target.value);
            attempt.current = null;
          }}
          aria-label="Student ID"
          placeholder="Student ID, like 054A"
          maxLength={20}
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          enterKeyHint="done"
        />
        <button className="primary" disabled={!student.trim() || busy}>
          Mark out
        </button>
      </form>
      <p className="error" role="alert" hidden={!err}>
        {err}
      </p>
      {s.bathroom_out.length ? (
        <ul className="bath-list">
          {s.bathroom_out.map((v) => {
            const m = minsAway(v);
            return (
              <li key={v.id}>
                <strong className="mono">{v.student_id}</strong>
                <span className="when" data-late={m >= LATE_MIN}>
                  left {clock(v.left_ms)} · {m < 1 ? "just now" : `${m} min`}
                </span>
                <button onClick={() => back(v)}>Returned</button>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="hint">Nobody is out.</p>
      )}
      {s.bathroom_back.length > 0 && (
        <details>
          <summary>Recently returned ({s.bathroom_back.length})</summary>
          <p className="mono">
            {[...s.bathroom_back]
              .reverse()
              .map((v) => `${v.student_id} ${clock(v.left_ms)}–${clock(v.back_ms!)}`)
              .join(" · ")}
          </p>
        </details>
      )}
    </section>
  );
}
