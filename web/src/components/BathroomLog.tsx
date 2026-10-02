import { useEffect, useRef, useState } from "react";
import { api, ApiError, post, serverNow, type Snapshot, type StudentLookup } from "../api";
import { useDebounced } from "../hooks";

type Visit = Snapshot["bathroom_out"][number];

const clock = (ms: number) => new Date(ms).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
const mins = (a: number, b: number) => Math.max(0, Math.floor((a - b) / 60_000));
const LATE_MIN = 10; // rows past this are highlighted (wireframe)

/**
 * Proctor · Bathroom log. Type an ID, Mark out; Returned when they are back.
 * One list, one row shape: students out now first, then the ones who came back, faded
 * (the same way deleted rooms and clarifications look). The parent re-renders every second,
 * so "out for" stays live without its own timer.
 */
export function BathroomLog({ s, setData }: { s: Snapshot; setData: (s: Snapshot) => void }) {
  const [student, setStudent] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [who, setWho] = useState<{ id: string; r: StudentLookup } | null>(null);
  // One id per attempt, reused if the request has to be retried, so a slow network can never log
  // the same student twice (invariant 3). Typing something else starts a new attempt.
  const attempt = useRef<string | null>(null);
  const base = `/api/rooms/${s.room_id}/bathroom`;

  // Who is this? Looked up once typing pauses; a late answer for an old ID is never shown.
  // Failing quietly is right: the name is a help, never a gate (marking out works without it).
  const typed = useDebounced(student.trim().toUpperCase(), 300);
  useEffect(() => {
    if (typed.length < 2) return;
    let live = true;
    api<StudentLookup>(`/api/roster/lookup?id=${encodeURIComponent(typed)}`)
      .then((r) => live && r && setWho({ id: typed, r }))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [typed]);
  const shown = who && who.id === student.trim().toUpperCase() ? who.r : null;
  const elsewhere = shown?.student?.room && shown.student.room.toLowerCase() !== s.room_name.toLowerCase();

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

  const returned = [...s.bathroom_back].reverse(); // most recent first
  const row = (v: Visit) => {
    const out = v.back_ms === null;
    const m = mins(out ? serverNow() : v.back_ms!, v.left_ms);
    return (
      <li key={v.id} className={out ? "visit" : "visit done"} data-late={out && m >= LATE_MIN}>
        <span className="bwho">
          <strong className="mono">{v.student_id}</strong>
          {v.student_name && <small>{v.student_name}</small>}
        </span>
        <span className="btime">
          <b>{m < 1 ? (out ? "Just now" : "Under 1 min") : `${m} min`}</b>
          <small>{out ? `left ${clock(v.left_ms)}` : `${clock(v.left_ms)}\u2013${clock(v.back_ms!)}`}</small>
        </span>
        {out && <button onClick={() => back(v)}>Returned</button>}
      </li>
    );
  };
  // One flat, keyed list: when a student comes back their row keeps its identity (it fades and
  // moves under "Back") instead of being thrown away and rebuilt, so nothing re-animates.
  const items = [
    ...s.bathroom_out.map(row),
    ...(s.bathroom_out.length > 0 && returned.length > 0 ? [<li key="sep" className="sep">Back</li>] : []),
    ...returned.map(row),
  ];

  return (
    <section className="bath" aria-labelledby="bath-h">
      <div className="bath-head">
        <h2 id="bath-h">Bathroom</h2>
        <span className={s.students_out > 0 ? "pill" : "muted"} aria-live="polite">
          {s.students_out > 0 ? `${s.students_out} out` : "Nobody out"}
        </span>
      </div>
      <form className="row bath-in" onSubmit={markOut}>
        <input
          value={student}
          onChange={(e) => {
            setStudent(e.target.value);
            attempt.current = null;
          }}
          aria-label="Student ID"
          aria-describedby="bath-who"
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
      {/* Always one line tall, so the list never jumps while someone types. */}
      <p id="bath-who" className="who-line" aria-live="polite">
        {shown?.student ? (
          <>
            <strong>{shown.student.name || "No name on file"}</strong>
            {shown.student.school && <span className="muted"> · {shown.student.school}</span>}
            {elsewhere && <span className="warn"> · assigned to {shown.student.room}</span>}
          </>
        ) : shown?.roster_loaded ? (
          <span className="muted">Not on the roster. You can still mark them out.</span>
        ) : null}
      </p>
      <p className="error" role="alert" hidden={!err}>
        {err}
      </p>
      {items.length === 0 ? <p className="hint">Students you mark out will show up here.</p> : <ul className="bath-list">{items}</ul>}
    </section>
  );
}
