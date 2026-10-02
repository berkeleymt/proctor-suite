import { useEffect, useRef, useState, type ReactNode } from "react";
import { post } from "../api";
import { go } from "../main";

type Tab = "timers" | "clarifications" | "bathroom" | "roster";

/** Admin page switcher (wireframe: tabs). */
export function AdminTabs({ active }: { active: Tab }) {
  const tab = (id: typeof active, label: string, path: string) => (
    <a className="tab" href={path} aria-current={active === id ? "page" : undefined} onClick={(e) => (e.preventDefault(), go(path))}>
      {label}
    </a>
  );
  return (
    <nav className="tabs" aria-label="Admin">
      {tab("timers", "Timers", "/admin")}
      {tab("clarifications", "Clarifications", "/admin/clarifications")}
      {tab("bathroom", "Bathroom", "/admin/bathroom")}
      {tab("roster", "Roster", "/admin/roster")}
    </nav>
  );
}

/** Log out, same button on every admin screen. */
export function LogoutButton() {
  return (
    <button
      onClick={async () => {
        await post("/api/auth/logout?surface=staff").catch(() => {});
        go("/login");
      }}
    >
      Log out
    </button>
  );
}

const TAB_LABEL = { timers: "Timers", clarifications: "Clarifications", bathroom: "Bathroom log", roster: "Roster" } as const;

/**
 * The admin header, one component for every admin tab. Wide screens: tabs, summary, light and
 * buttons in one row. Narrow screens: a menu button, the current tab, and the light; the menu
 * opens over the page (nothing shifts) with everything stacked in the same order, minus the light.
 */
export function AdminBar({ active, online, summary, deleted, children }: { active: keyof typeof TAB_LABEL; online: boolean; summary: ReactNode; deleted?: { count: number; shown: boolean; toggle: () => void }; children?: ReactNode }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);
  return (
    <header className={`bar abar ${open ? "open" : ""}`} ref={box}>
      <button className="burger" aria-label="Menu" aria-expanded={open} aria-controls="admin-menu" onClick={() => setOpen(!open)}>
        <i /><i /><i />
      </button>
      <span className="cur">{TAB_LABEL[active]}</span>
      <div className="abar-menu" id="admin-menu" onClick={(e) => (e.target as HTMLElement).closest("button, a") && setOpen(false)}>
        <AdminTabs active={active} />
        <span className="muted">
          <span>{summary}</span>
          {deleted && deleted.count > 0 && (
            <>
              <span className="sep"> · </span>
              <button className="link" onClick={deleted.toggle}>
                {deleted.shown ? "Hide" : "Show"} deleted ({deleted.count})
              </button>
            </>
          )}
        </span>
        <Dot online={online} className="desk-only" />
        {children}
        <LogoutButton />
      </div>
      <Dot online={online} className="mob-only" />
    </header>
  );
}

/** The connection light. Same look and position on every screen (green = connected). */
export function Dot({ online, className = "" }: { online: boolean; className?: string }) {
  return <span className={`dot ${online ? "ok" : "bad"} ${className}`} role="img" aria-label={online ? "Connected" : "Offline"} title={online ? "Connected" : "Offline: retrying"} />;
}

/** Every dialog in the app: slides up, Esc or a click outside closes it, same title and button layout. */
export function Sheet({ title, onClose, children, onSubmit }: { title: string; onClose: () => void; children: ReactNode; onSubmit?: () => void }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  const Tag = onSubmit ? "form" : "div";
  return (
    <div className="scrim" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <Tag
        className="sheet stack"
        role="dialog"
        aria-modal
        aria-label={title}
        {...(onSubmit ? { onSubmit: (e: React.FormEvent) => { e.preventDefault(); onSubmit(); } } : {})}
      >
        <h2>{title}</h2>
        {children}
      </Tag>
    </div>
  );
}

/** "More actions" popover for a table row. */
export function Menu({ label, items }: { label: string; items: { label: string; onSelect: () => void; danger?: boolean; disabled?: boolean }[] }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);
  return (
    <span className="menu" ref={box}>
      <button className="menu-btn" aria-label={label} aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}>
        ⋯
      </button>
      {open && (
        <div className="menu-list" role="menu">
          {items.map((it) => (
            <button
              key={it.label}
              role="menuitem"
              className={it.danger ? "bad" : ""}
              disabled={it.disabled}
              onClick={() => {
                setOpen(false);
                it.onSelect();
              }}
            >
              {it.label}
            </button>
          ))}
        </div>
      )}
    </span>
  );
}

/** A button that opens a floating panel (click outside or Esc closes). For pickers and long lists. */
export function Popover({ label, children, className = "" }: { label: ReactNode; children: ReactNode; className?: string }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);
  return (
    <span className={`menu ${className}`} ref={box}>
      <button type="button" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(!open)}>
        {label} <span aria-hidden>{open ? "▴" : "▾"}</span>
      </button>
      {open && <div className="pop" role="dialog">{children}</div>}
    </span>
  );
}
