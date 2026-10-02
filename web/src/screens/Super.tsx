import { useEffect, useRef, useState } from "react";
import { api, ApiError, del, patch, post, type SuperAdmin, type SuperSettings } from "../api";
import { BrandMark, loadBrand, useBrand, usePageTitle } from "../brand";
import { Sheet } from "../components/ui";

const GSI = "https://accounts.google.com/gsi/client";
type Credential = { credential?: string };
type Gsi = { accounts: { id: { initialize: (o: { client_id: string; callback: (r: Credential) => void }) => void; renderButton: (el: HTMLElement, o: Record<string, unknown>) => void } } };
const msg = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong. Try again.");

/** Load Google's sign-in script, only on this page (it is not needed anywhere else). */
function loadGsi(): Promise<Gsi> {
  const w = window as unknown as { google?: Gsi };
  if (w.google?.accounts) return Promise.resolve(w.google);
  return new Promise((ok, no) => {
    const s = document.createElement("script");
    s.src = GSI;
    s.async = true;
    s.onload = () => (w.google ? ok(w.google) : no(new Error("no google")));
    s.onerror = () => no(new Error("Couldn't load Google sign-in. Check your connection."));
    document.head.appendChild(s);
  });
}

/** Super-admin page (wireframe: /super). Google sign-in, then name/icon, passwords, super-admins. */
export function Super() {
  usePageTitle("Super admin");
  const [me, setMe] = useState<string | null | undefined>(undefined); // undefined = checking
  useEffect(() => {
    api<{ email: string }>("/api/super/me").then((r) => setMe(r!.email), () => setMe(null));
  }, []);
  if (me === undefined) return <main className="center" />;
  return me === null ? <SignIn onDone={setMe} /> : <Panel email={me} out={() => setMe(null)} />;
}

function SignIn({ onDone }: { onDone: (email: string) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const cfg = await api<{ google_client_id: string | null }>("/api/auth/super-config");
        if (!cfg?.google_client_id) return setErr("Google sign-in isn't set up on this server yet. Add GOOGLE_CLIENT_ID to .env.");
        const g = await loadGsi();
        if (!live || !box.current) return;
        g.accounts.id.initialize({
          client_id: cfg.google_client_id,
          callback: async (r) => {
            setErr("");
            try {
              onDone((await post<{ email: string }>("/api/auth/super-login", { credential: r.credential }))!.email);
            } catch (e) {
              setErr(msg(e));
            }
          },
        });
        g.accounts.id.renderButton(box.current, { theme: "outline", size: "large", width: 300 });
      } catch (e) {
        setErr(msg(e));
      }
    })();
    return () => void (live = false);
  }, [onDone]);
  return (
    <main className="center">
      <div className="card stack">
        <BrandMark />
        <p className="muted center-text">Super-admin access to site configurations, passwords, and user management.</p>
        <div className="gsi" ref={box} />
        <p className="error" role="alert" hidden={!err}>{err}</p>
      </div>
    </main>
  );
}

function Panel({ email, out }: { email: string; out: () => void }) {
  const [s, setS] = useState<SuperSettings | null>(null);
  const [admins, setAdmins] = useState<SuperAdmin[]>([]);
  const fail = (e: unknown, set: (m: string) => void) => (e instanceof ApiError && e.status === 401 ? out() : set(msg(e)));
  useEffect(() => {
    Promise.all([api<SuperSettings>("/api/super/settings"), api<{ admins: SuperAdmin[] }>("/api/super/admins")])
      .then(([a, b]) => (setS(a), setAdmins(b!.admins)))
      .catch((e) => fail(e, () => {}));
  }, []);
  const logout = async () => {
    await post("/api/auth/super-logout").catch(() => {});
    out();
  };
  return (
    <main>
      <header className="bar">
        <h1>Super admin</h1>
        <span className="muted">{email}</span>
        <button onClick={logout}>Log out</button>
      </header>
      <div className="super">
        {s && <Site s={s} setS={setS} fail={fail} />}
        {s && <Passwords s={s} setS={setS} fail={fail} />}
        {s && <ContestDojo s={s} setS={setS} fail={fail} />}
        <Admins admins={admins} setAdmins={setAdmins} me={email} fail={fail} />
      </div>
    </main>
  );
}
type Fail = (e: unknown, set: (m: string) => void) => void;

function Site({ s, setS, fail }: { s: SuperSettings; setS: (s: SuperSettings) => void; fail: Fail }) {
  const [name, setName] = useState(s.app_name);
  const [icon, setIcon] = useState(s.app_icon);
  const [err, setErr] = useState("");
  const [saved, setSaved] = useState(false);
  const live = useBrand();
  const dirty = name.trim() !== s.app_name || icon.trim() !== s.app_icon;
  const save = async () => {
    setErr("");
    try {
      setS((await patch<SuperSettings>("/api/super/settings", { app_name: name, app_icon: icon }))!);
      await loadBrand(); // this tab picks up the new title and icon at once
      setSaved(true);
    } catch (e) {
      fail(e, setErr);
    }
  };
  return (
    <section className="block">
      <h2>Name and icon</h2>
      <p className="muted">Shown on the login page, the browser tab and the tab icon. Saved here, they replace APP_NAME and APP_ICON in .env.</p>
      <label>
        Name
        <input value={name} maxLength={40} onChange={(e) => (setName(e.target.value), setSaved(false))} />
      </label>
      <label>
        Icon: a link, or a path to a file on this site
        <span className="row">
          <input value={icon} maxLength={500} placeholder="/logo.png or https://…" onChange={(e) => (setIcon(e.target.value), setSaved(false))} />
          {live.icon && <img className="icon-preview" src={live.icon} alt="Current icon" />}
        </span>
        <small>A file in web/public/ is /its-name. Leave empty for no icon.</small>
      </label>
      <p className="error" role="alert" hidden={!err}>{err}</p>
      <div className="row">
        <button className="primary" disabled={!dirty || !name.trim()} onClick={save}>Save</button>
        {saved && !dirty && <span className="muted">Saved.</span>}
      </div>
    </section>
  );
}

function ContestDojo({ s, setS, fail }: { s: SuperSettings; setS: (s: SuperSettings) => void; fail: Fail }) {
  const [token, setToken] = useState(s.contestdojo_token);
  const [ev, setEv] = useState(s.contestdojo_event_id);
  const [err, setErr] = useState("");
  const [saved, setSaved] = useState(false);
  const dirty = token.trim() !== s.contestdojo_token || ev.trim() !== s.contestdojo_event_id;
  const save = async () => {
    setErr("");
    try {
      setS((await patch<SuperSettings>("/api/super/settings", { contestdojo_token: token, contestdojo_event_id: ev }))!);
      setSaved(true);
    } catch (e) {
      fail(e, setErr);
    }
  };
  return (
    <section className="block">
      <h2>ContestDojo</h2>
      <p className="muted">Used by Admin → Roster → Sync. Saved here, they replace CONTESTDOJO_API_TOKEN and CONTESTDOJO_EVENT_ID in .env.</p>
      <label>
        API token
        <input value={token} maxLength={200} autoComplete="off" onChange={(e) => (setToken(e.target.value), setSaved(false))} />
      </label>
      <label>
        Event ID
        <input value={ev} maxLength={100} autoComplete="off" onChange={(e) => (setEv(e.target.value), setSaved(false))} />
      </label>
      <p className="error" role="alert" hidden={!err}>{err}</p>
      <div className="row">
        <button className="primary" disabled={!dirty} onClick={save}>Save</button>
        {saved && !dirty && <span className="muted">Saved.</span>}
      </div>
    </section>
  );
}

function Passwords({ s, setS, fail }: { s: SuperSettings; setS: (s: SuperSettings) => void; fail: Fail }) {
  type Which = "room_password" | "admin_password";
  const [shown, setShown] = useState<Which | null>(null);
  const [edit, setEdit] = useState<Which | null>(null);
  const [draft, setDraft] = useState("");
  const [logOut, setLogOut] = useState(false);
  const [err, setErr] = useState("");
  const rows: [Which, string, string][] = [
    ["room_password", "Proctor password (all rooms)", "everyone signed in to a room"],
    ["admin_password", "Admin password", "every admin"],
  ];
  const save = async () => {
    setErr("");
    try {
      setS((await patch<SuperSettings>("/api/super/settings", { [edit!]: draft, log_out_old: logOut }))!);
      setEdit(null);
      setDraft("");
    } catch (e) {
      fail(e, setErr);
    }
  };
  return (
    <section className="block">
      <h2>Passwords</h2>
      {rows.map(([k, label]) => (
        <div className="secret" key={k}>
          <span className="label">{label}</span>
          {edit === k ? (
            <>
              <input autoFocus value={draft} minLength={8} maxLength={100} onChange={(e) => setDraft(e.target.value)} placeholder="New password (8+ characters)" autoComplete="off" onKeyDown={(e) => e.key === "Enter" && draft.length >= 8 && save()} />
              <button onClick={() => (setEdit(null), setDraft(""), setErr(""))}>Cancel</button>
              <button className="primary" disabled={draft.length < 8} onClick={save}>Save</button>
            </>
          ) : (
            <>
              <code>{shown === k ? s[k] : "••••••••"}</code>
              <button onClick={() => setShown(shown === k ? null : k)}>{shown === k ? "Hide" : "Show"}</button>
              <button onClick={() => (setEdit(k), setDraft(""), setErr(""))}>Change…</button>
            </>
          )}
        </div>
      ))}
      <label className="check-row">
        <input type="checkbox" checked={logOut} onChange={(e) => setLogOut(e.target.checked)} />
        Log out everyone signed in with the old password when I change one
      </label>
      <p className="error" role="alert" hidden={!err}>{err}</p>
      <p className="muted">Changes apply at once, no redeploy. They replace ROOM_PASSWORD and ADMIN_PASSWORD in .env.</p>
    </section>
  );
}

function Admins({ admins, setAdmins, me, fail }: { admins: SuperAdmin[]; setAdmins: (a: SuperAdmin[]) => void; me: string; fail: Fail }) {
  const [email, setEmail] = useState("");
  const [err, setErr] = useState("");
  const [gone, setGone] = useState<SuperAdmin | null>(null);
  const run = async (f: () => Promise<{ admins: SuperAdmin[] } | null>) => {
    setErr("");
    try {
      setAdmins((await f())!.admins);
      return true;
    } catch (e) {
      fail(e, setErr);
      return false;
    }
  };
  const add = async () => (await run(() => post("/api/super/admins", { email }))) && setEmail("");
  return (
    <section className="block">
      <h2>Super-admins</h2>
      <p className="muted">Only these Google accounts can open this page.</p>
      <div>
        {admins.map((a) => (
          <div className="who" key={a.email}>
            <span>
              {a.email}
              {a.email === me && <span className="muted"> (you)</span>}
              <br />
              <small className="muted">{a.source === "env" ? "Set in .env (SUPER_ADMIN_EMAILS)" : `Added by ${a.added_by}`}</small>
            </span>
            {a.source === "added" && a.email !== me && <button className="bad" onClick={() => setGone(a)}>Remove…</button>}
          </div>
        ))}
      </div>
      <form className="row" onSubmit={(e) => (e.preventDefault(), email.trim() && add())}>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@berkeley.edu" aria-label="Email to add" />
        <button className="primary" disabled={!email.trim()}>Add</button>
      </form>
      <p className="error" role="alert" hidden={!err}>{err}</p>
      {gone && (
        <Sheet title={`Remove ${gone.email}?`} onClose={() => setGone(null)}>
          <p className="muted">They are signed out of this page right away and can&apos;t sign back in. You can add them again later.</p>
          <div className="row end">
            <button onClick={() => setGone(null)}>Cancel</button>
            <button className="danger" onClick={async () => (await run(() => del(`/api/super/admins/${encodeURIComponent(gone.email)}`)), setGone(null))}>Remove</button>
          </div>
        </Sheet>
      )}
    </section>
  );
}
