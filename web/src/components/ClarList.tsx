import { useEffect, useLayoutEffect, useRef } from "react";
import type { Clar } from "../api";

/** Plain text; lines starting "- " become bullets (the markdown subset we support so far). */
export function ClarBody({ body }: { body: string }) {
  const out: React.ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length) out.push(<ul key={`u${out.length}`}>{list.map((t, i) => <li key={i}>{t}</li>)}</ul>);
    list = [];
  };
  for (const line of body.split("\n")) {
    if (line.startsWith("- ")) list.push(line.slice(2));
    else if (line.trim()) (flush(), out.push(<p key={`p${out.length}`}>{line}</p>));
  }
  flush();
  return <>{out}</>;
}

/** Projector clarifications: oldest first; the font shrinks until everything fits its box. */
export function FitList({ items }: { items: Pick<Clar, "id" | "body">[] }) {
  const box = useRef<HTMLDivElement>(null);
  const fit = () => {
    const el = box.current;
    if (!el) return;
    let px = 44;
    el.style.fontSize = `${px}px`;
    while (px > 12 && el.scrollHeight > el.clientHeight) el.style.fontSize = `${(px -= 2)}px`;
  };
  useLayoutEffect(fit, [items]);
  useEffect(() => {
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, []);
  return (
    <div className="clars" ref={box} aria-live="polite">
      {items.map((c) => (
        <div className="clar" key={c.id}>
          <ClarBody body={c.body} />
        </div>
      ))}
    </div>
  );
}
