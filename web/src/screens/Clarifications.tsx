import { useEffect, useState } from "react";
import { api, ApiError, del, patch, post, type Clar, type Snapshot } from "../api";
import { go } from "../main";
import { AdminTabs, Popover, Sheet } from "../components/ui";
import { ClarItem } from "../components/ClarList";

type Rooms = { rooms: Snapshot[] };
type Room = { id: string; name: string; test: string };
type Group = { label: string; ids: string[] };
type Dialog = { kind: "hide" | "delete" | "edit"; c: Clar; room?: string; draft?: string };

const hhmm = (ms: number) => new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
const buildingOf = (name: string) => name.match(/^(.*?)\s+\d[\w-]*$/)?.[1] ?? name.split(" ")[0]; // "Wheeler Hall 150" -> "Wheeler Hall"
const RETRACTED = "**Retracted:** please disregard this clarification.";

/** "All Evans" and "All <test>" quick picks. Skipped when they'd match nothing new. */
function groupsOf(rooms: Room[]): Group[] {
  const by = (key: (r: Room) => string) => {
    const g = new Map<string, string[]>();
    rooms.forEach((r) => key(r) && g.set(key(r), [...(g.get(key(r)) ?? []), r.id]));
    return [...g].filter(([, ids]) => ids.length > 1 && ids.length < rooms.length).map(([k, ids]) => ({ label: `All ${k}`, ids }));
  };
  return [...by((r) => buildingOf(r.name)), ...by((r) => r.test)];
}

/** Where a post goes, in a few words: never one pill per room (there are 200+). */
function describe(c: Clar, rooms: Room[], groups: Group[], names: Map<string, string>): string {
  const gone = new Set(c.removed_room_ids);
  const t = (c.room_ids ?? rooms.map((r) => r.id)).filter((id) => !gone.has(id));
  if (t.length === 0) return "No rooms";
  if (c.room_ids === null) return gone.size ? `All rooms except ${gone.size}` : "All rooms";
  if (t.length === rooms.length) return "All rooms";
  const set = new Set(t);
  const g = groups.find((x) => x.ids.length === set.size && x.ids.every((i) => set.has(i)));
  if (g) return g.label;
  return t.length <= 3 ? t.map((id) => names.get(id) ?? id).join(", ") : `${t.length} rooms`;
}

/** All rooms / All <building> / All <test> / Clear, plus a small searchable list for single rooms. */
function RoomPicker({ rooms, groups, sel, setSel }: { rooms: Room[]; groups: Group[]; sel: Set<string>; setSel: (s: Set<string>) => void }) {
  const [q, setQ] = useState("");
  const toggle = (ids: string[]) => {
    const n = new Set(sel);
    const on = ids.every((i) => n.has(i));
    ids.forEach((i) => (on ? n.delete(i) : n.add(i)));
    setSel(n);
  };
  const shown = rooms.filter((r) => r.name.toLowerCase().includes(q.trim().toLowerCase()));
  const allShown = shown.length > 0 && shown.every((r) => sel.has(r.id));
  return (
    <div className="chips">
      <button className="chip" aria-pressed={rooms.length > 0 && sel.size === rooms.length} onClick={() => setSel(new Set(rooms.map((r) => r.id)))}>All rooms</button>
      {groups.map((g) => (
        <button key={g.label} className="chip" aria-pressed={g.ids.every((i) => sel.has(i))} onClick={() => toggle(g.ids)}>{g.label}</button>
      ))}
      <button className="chip" disabled={sel.size === 0} onClick={() => setSel(new Set())}>Clear</button>
      <Popover label="Pick rooms">
        <input type="search" autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find a room" aria-label="Find a room" />
        <div className="scroll">
          {shown.map((r) => (
            <label className="check" key={r.id}>
              <input type="checkbox" checked={sel.has(r.id)} onChange={() => toggle([r.id])} />
              <span>{r.name}</span>
              <small>{r.test}</small>
            </label>
          ))}
          {shown.length === 0 && <p className="muted">No rooms match.</p>}
        </div>
        {shown.length > 0 && (
          <button type="button" className="link" onClick={() => toggle(shown.map((r) => r.id))}>
            {allShown ? "Unselect" : "Select"} the {shown.length} shown
          </button>
        )}
      </Popover>
    </div>
  );
}

/** Where a posted clarification is showing: a short summary, and a scrollable per-room list with Hide / Delete. */
function Where({ c, rooms, groups, names, onHide, onDelete }: { c: Clar; rooms: Room[]; groups: Group[]; names: Map<string, string>; onHide: (room: string, hidden: boolean) => void; onDelete: (room: string) => void }) {
  const [q, setQ] = useState("");
  const gone = new Set(c.removed_room_ids);
  const hereHidden = new Set(c.hidden_room_ids);
  const ids = [...new Set([...(c.room_ids ?? rooms.map((r) => r.id)), ...c.removed_room_ids])];
  const name = (id: string) => names.get(id) ?? id;
  const rows = ids
    .filter((id) => name(id).toLowerCase().includes(q.trim().toLowerCase()))
    .sort((a, b) => Number(gone.has(a)) - Number(gone.has(b)) || name(a).localeCompare(name(b), undefined, { numeric: true }));
  const status = [c.hidden && "Hidden everywhere", hereHidden.size > 0 && `Hidden in ${hereHidden.size}`, c.room_ids !== null && gone.size > 0 && `Deleted from ${gone.size}`].filter(Boolean).join(" · ");
  return (
    <div className="where">
      <span className="pill">{describe(c, rooms, groups, names)}</span>
      {status && <span className="muted">{status}</span>}
      <Popover label={`Rooms (${ids.length})`}>
        {c.hidden && <p className="muted">Hidden everywhere. Unhide it to change single rooms.</p>}
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find a room" aria-label="Find a room" />
        <div className="scroll">
          {rows.map((id) => (
            <div className="roomrow" key={id}>
              <span className="nm">{name(id)}</span>
              <span className="muted">{gone.has(id) ? "Deleted here" : c.hidden ? "Hidden" : hereHidden.has(id) ? "Hidden here" : "Showing"}</span>
              {!gone.has(id) && (
                <>
                  <button disabled={c.hidden} onClick={() => onHide(id, !hereHidden.has(id))}>{hereHidden.has(id) ? "Unhide" : "Hide"}</button>
                  <button className="bad" onClick={() => onDelete(id)}>Delete…</button>
                </>
              )}
            </div>
          ))}
          {rows.length === 0 && <p className="muted">No rooms match.</p>}
        </div>
      </Popover>
    </div>
  );
}

/** Edit: the old wording stays on screen, crossed out, so the preview shows exactly what students will see. */
function EditSheet({ c, draft: first, onClose, onSave }: { c: Clar; draft?: string; onClose: () => void; onSave: (body: string) => void }) {
  const [draft, setDraft] = useState(first ?? c.body);
  const same = !draft.trim() || draft.trim() === c.body;
  return (
    <Sheet title="Edit clarification" onClose={onClose} onSubmit={() => !same && onSave(draft)}>
      <p className="muted">Students keep seeing the old wording, crossed out, with your new text after it.</p>
      <label>
        New wording
        <textarea autoFocus rows={4} maxLength={2000} value={draft} onChange={(e) => setDraft(e.target.value)} />
      </label>
      <div className="preview">
        <span className="muted">What students will see</span>
        <ClarItem c={{ id: c.id, previous: [...c.previous, c.body], body: draft.trim() || "…" }} />
      </div>
      <div className="row end">
        <button type="button" onClick={onClose}>Cancel</button>
        <button className="primary" disabled={same}>Save edit</button>
      </div>
    </Sheet>
  );
}

/** Admin · Clarifications (wireframe): composer with preview, room picker, posted list. */
export function Clarifications() {
  const [rooms, setRooms] = useState<Room[] | null>(null);
  const [list, setList] = useState<Clar[]>([]);
  const [body, setBody] = useState("");
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [dialog, setDialog] = useState<Dialog | null>(null);

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
  const groups = groupsOf(rooms);
  const act = async (f: () => Promise<unknown>) => {
    setErr("");
    setDialog(null);
    try {
      await f();
      await load();
    } catch (e) {
      fail(e);
    }
  };
  const url = (c: Clar) => `/api/staff/clarifications/${c.id}`;
  const hide = (c: Clar, hidden: boolean, room?: string) => act(() => patch(url(c), { hidden, ...(room ? { room_id: room } : {}) }));
  const wipe = (c: Clar, room?: string) => act(() => del(`${url(c)}${room ? `?room_id=${encodeURIComponent(room)}` : ""}`));

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

  const where = (d: Dialog) => (d.room ? (names.get(d.room) ?? d.room) : null);
  return (
    <main className="admin">
      <header className="bar">
        <AdminTabs active="clarifications" />
      </header>
      <section className="stack composer">
        <div className="compose-grid">
          <label>
            <b>New clarification</b>
            <textarea rows={6} maxLength={2000} value={body} onChange={(e) => setBody(e.target.value)} placeholder={"Problem 7: “integer” means **positive** integer, so $n \\ge 1$.\n- Start a line with “- ” for a bullet point"} />
            <small>{"Supports markdown and math LaTeX: **bold**, *italic*, - bullets, $x^2$, $$\\frac{a}{b}$$."}</small>
          </label>
          <div className="preview" aria-label="Preview">
            <span className="muted"><b>Preview</b></span>
            {body.trim() ? <ClarItem c={{ id: "preview", body, previous: [] }} /> : <p className="muted">This will show the way students see the clarification.</p>}
          </div>
        </div>
        <div className="stack">
          <RoomPicker rooms={rooms} groups={groups} sel={sel} setSel={setSel} />
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
            <Where c={c} rooms={rooms} groups={groups} names={names} onHide={(room, h) => (h ? setDialog({ kind: "hide", c, room }) : hide(c, false, room))} onDelete={(room) => setDialog({ kind: "delete", c, room })} />
            <div className="text"><ClarItem c={c} /></div>
            <div className="actions">
              <button onClick={() => setDialog({ kind: "edit", c })}>Edit</button>
              <button onClick={() => (c.hidden ? hide(c, false) : setDialog({ kind: "hide", c }))}>{c.hidden ? "Unhide" : "Hide"}</button>
              <button className="bad" onClick={() => setDialog({ kind: "delete", c })}>Delete…</button>
            </div>
          </article>
        ))}
      </section>
      {dialog?.kind === "edit" && <EditSheet c={dialog.c} draft={dialog.draft} onClose={() => setDialog(null)} onSave={(b) => act(() => patch(url(dialog.c), { body: b }))} />}
      {dialog?.kind === "hide" && (
        <Sheet title={dialog.room ? `Hide it in ${where(dialog)}?` : "Hide this clarification?"} onClose={() => setDialog(null)}>
          <p className="muted">
            {dialog.room ? "Students there may already have read it, and hiding just removes it from their screen with no sign it was taken back." : "Students may already have read it. Hiding makes it vanish from their screens with no sign it was taken back."}{" "}
            If you are retracting it, edit it instead: they will see the old text crossed out and your note after it. Editing changes it in every room it was posted to.
          </p>
          <div className="row end">
            <button onClick={() => setDialog(null)}>Cancel</button>
            <button className="danger" onClick={() => hide(dialog.c, true, dialog.room)}>Hide anyway</button>
            <button className="primary" autoFocus onClick={() => setDialog({ kind: "edit", c: dialog.c, draft: RETRACTED })}>Edit instead</button>
          </div>
        </Sheet>
      )}
      {dialog?.kind === "delete" && (
        <Sheet title={dialog.room ? `Delete it from ${where(dialog)}?` : "Delete this clarification?"} onClose={() => setDialog(null)}>
          <p className="muted">
            {dialog.room ? `It is wiped from ${where(dialog)} for good and stays in the other rooms.` : "This will wipe it from every room and from the system for good."} You can&apos;t undo this, and students leave no trace of it. Use Hide if you might want it back, or Edit if students already saw it.
          </p>
          <div className="row end">
            <button onClick={() => setDialog(null)}>Cancel</button>
            <button className="danger" onClick={() => wipe(dialog.c, dialog.room)}>Delete</button>
          </div>
        </Sheet>
      )}
    </main>
  );
}
