import { useEffect, useState } from "react";
import { api, ApiError, patch, post, type Clar, type Snapshot } from "../api";
import { go } from "../main";
import { AdminTabs } from "../components/ui";
import { ClarBody } from "../components/ClarList";

type Rooms = { rooms: Snapshot[] };
type Room = { id: string; name: string; test: string };
const hhmm = (ms: number) => new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

/** Admin · Clarifications (wireframe): composer + room chips + posted list with Hide/Unhide. */
export function Clarifications() {
  const [rooms, setRooms] = useState<Room[] | null>(null);
  const [list, setList] = useState<Clar[]>([]);
  const [body, setBody] = useState("");
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const fail = (e: unknown) => (e instanceof ApiError && e.status === 401 ? go("/login") : setErr(e instanceof Error ? e.message : "Something went wrong."));
  const load = () =>
    Promise.all([api<Rooms>("/api/staff/rooms"), api<{ clarifications: Clar[] }>("/api/staff/clarifications")])
      .then(([r, c]) => {
        setRooms(r!.rooms.filter((x) => !x.deleted).map((x) => ({ id: x.room_id, name: x.room_name, test: x.test_name })));
        setList(c!.clarifications);
      })
      .catch(fail);
  useEffect(() => void load(), []);
  if (!rooms) return <main className="center" />;

  const names = new Map(rooms.map((r) => [r.id, r.name]));
  const group = (key: (r: Room) => string) => {
    const g = new Map<string, string[]>();
    rooms.forEach((r) => g.set(key(r), [...(g.get(key(r)) ?? []), r.id]));
    return [...g].filter(([, ids]) => ids.length > 1 && ids.length < rooms.length);
  };
  const pick = (ids: string[]) => setSel(new Set(ids));
  const toggle = (id: string) => setSel((s) => (s.has(id) ? new Set([...s].filter((x) => x !== id)) : new Set(s).add(id)));

  const submit = async () => {
    setBusy(true);
    setErr("");
    try {
      const all = sel.size === rooms.length; // everyone selected = "All rooms" (new rooms get it too)
      await post<Clar>("/api/staff/clarifications", { body, room_ids: all ? null : [...sel] });
      setBody("");
      await load();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };
  const hide = (c: Clar) =>
    patch<Clar>(`/api/staff/clarifications/${c.id}`, { hidden: !c.hidden })
      .then((x) => setList((l) => l.map((y) => (y.id === x!.id ? x! : y))))
      .catch(fail);

  return (
    <main className="admin">
      <header className="bar">
        <AdminTabs active="clarifications" />
      </header>
      <section className="stack composer">
        <label>
          New clarification
          <textarea rows={3} maxLength={2000} value={body} onChange={(e) => setBody(e.target.value)} placeholder={"Problem 7: “integer” means positive integer.\n- Start a line with “- ” for a bullet"} />
        </label>
        <div className="stack">
          <span className="muted">Send to</span>
          <div className="chips">
            <button className="chip" onClick={() => pick(rooms.map((r) => r.id))}>All rooms</button>
            <button className="chip" onClick={() => pick([])}>Clear</button>
            {group((r) => r.name.split(" ")[0]).map(([k, ids]) => (
              <button key={`b${k}`} className="chip" onClick={() => pick(ids)}>All {k}</button>
            ))}
            {group((r) => r.test).map(([k, ids]) => (
              <button key={`t${k}`} className="chip" onClick={() => pick(ids)}>{k} rooms</button>
            ))}
          </div>
          <div className="chips">
            {rooms.map((r) => (
              <button key={r.id} className="chip" aria-pressed={sel.has(r.id)} onClick={() => toggle(r.id)}>{r.name}</button>
            ))}
          </div>
          <p className="muted">{sel.size === 0 ? "Pick at least one room." : `Will post to ${sel.size} of ${rooms.length} rooms`}</p>
        </div>
        {err && <p className="error" role="alert">{err}</p>}
        <div className="row">
          <button className="primary" disabled={busy || !body.trim() || sel.size === 0} onClick={submit}>Post</button>
        </div>
      </section>
      <section className="posted">
        <h2>Posted</h2>
        {list.length === 0 && <p className="muted">Nothing posted yet.</p>}
        {list.map((c) => (
          <article key={c.id} className={`post ${c.hidden ? "off" : ""}`}>
            <time className="muted mono">{hhmm(c.created_at_ms)}</time>
            <div className="where">
              {c.room_ids === null ? <span className="pill">All rooms</span> : c.room_ids.slice(0, 4).map((id: string) => <span key={id} className="pill">{names.get(id) ?? id}</span>)}
              {c.room_ids !== null && c.room_ids.length > 4 && <span className="pill">+{c.room_ids.length - 4}</span>}
            </div>
            <div className="text"><ClarBody body={c.body} /></div>
            <button onClick={() => hide(c)}>{c.hidden ? "Unhide" : "Hide"}</button>
          </article>
        ))}
      </section>
    </main>
  );
}
