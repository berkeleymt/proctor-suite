import { useEffect, useState } from "react";
import { api, ApiError, post, type RoomOption } from "../api";
import { go } from "../main";
import { BrandMark, usePageTitle } from "../brand";
import { enterFullscreen, isDisplayWindow } from "../fullscreen";

const ADMIN = "__admin__";

export function Login() {
  usePageTitle();
  const q = new URLSearchParams(location.search);
  const surface = q.get("surface") === "display" ? "display" : "control";
  const [rooms, setRooms] = useState<RoomOption[] | null>(null);
  const [room, setRoom] = useState(q.get("room") ?? "");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<{ rooms: RoomOption[] }>("/api/auth/rooms")
      .then((r) => setRooms(r?.rooms ?? []))
      .catch(() => setErr("Can't reach the server. Retrying won't hurt; check your connection."));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!room || busy) return;
    if (surface === "display" && isDisplayWindow()) void enterFullscreen(); // this click is the permission
    setBusy(true);
    setErr("");
    try {
      if (room === ADMIN) {
        await post("/api/auth/staff-login", { username: "admin", password: pw });
        go("/admin");
      } else {
        await post("/api/auth/room-login", { room_id: room, password: pw, surface });
        go(surface === "display" ? "/display" : "/proctor");
      }
    } catch (e) {
      setErr(e instanceof ApiError && e.status === 401 ? "Wrong password for this room." : "Couldn't sign in. Try again.");
      setBusy(false);
    }
  }

  return (
    <main className="center">
      <form className="card stack" onSubmit={submit}>
        <BrandMark />
        {surface === "display" && <p className="muted">Signing in the projector display</p>}
        <label>
          Room
          <select value={room} onChange={(e) => setRoom(e.target.value)} disabled={!rooms}>
            <option value="" disabled>
              {rooms ? "Select a room" : "Loading…"}
            </option>
            {surface === "control" && <option value={ADMIN}>Admin</option>}
            {rooms?.map((r) => (
              <option key={r.room_id} value={r.room_id}>
                {r.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Password
          <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="current-password" />
        </label>
        <p className="error" role="alert" hidden={!err}>
          {err}
        </p>
        <button className="primary" disabled={!room || !pw || busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
