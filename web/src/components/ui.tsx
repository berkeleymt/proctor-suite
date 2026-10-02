import { useEffect, useRef, useState, type ReactNode } from "react";

/** The connection light. Same look and position on every screen (green = connected). */
export function Dot({ online }: { online: boolean }) {
  return <span className={`dot ${online ? "ok" : "bad"}`} role="img" aria-label={online ? "Connected" : "Offline"} title={online ? "Connected" : "Offline: retrying"} />;
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
