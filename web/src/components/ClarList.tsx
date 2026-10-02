import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import MarkdownIt from "markdown-it";
import mathPlugin from "@vscode/markdown-it-katex";
import "katex/dist/katex.min.css"; // bundled with its fonts: nothing is fetched from a CDN (invariant 6)
import type { Clar } from "../api";

/** Markdown + $inline$ / $$display$$ math. Raw HTML is off, so the output is safe to inject. */
const md = new MarkdownIt({ html: false, breaks: true, linkify: false }).use(mathPlugin, { throwOnError: false });

export function ClarBody({ body }: { body: string }) {
  const html = useMemo(() => md.render(body), [body]);
  return <div className="md" dangerouslySetInnerHTML={{ __html: html }} />;
}

type Item = Pick<Clar, "id" | "body" | "previous">;

/** One clarification as students see it: earlier wordings struck out and faded, then the current one. */
export function ClarItem({ c }: { c: Item }) {
  return (
    <div className="clar">
      {c.previous.map((p, i) => (
        <del className="was" key={i} title="Earlier wording, replaced">
          <ClarBody body={p} />
        </del>
      ))}
      <ClarBody body={c.body} />
    </div>
  );
}

const STEPS_VH = [2.5, 3.5, 4.5, 6, 8, 10, 12, 15]; // manual sizes, as % of screen height
const AUTO_MAX_VH = 11; // Auto never goes bigger than this, so one short line isn't absurd
const AUTO_MIN_PX = 14;
const AUTO_BACK_STEPS = 3; // Auto lands where three ¶− clicks from the largest size that fits would (PM, 2026-10-02)

/** The manual step closest to a pixel size. */
const nearestStep = (px: number) => {
  const vh = (px / window.innerHeight) * 100;
  return STEPS_VH.reduce((best, v, i) => (Math.abs(v - vh) < Math.abs(STEPS_VH[best] - vh) ? i : best), 0);
};
const KEY = "clarsize:display";

/** Projector clarification size: "auto" (largest that fits) or a fixed step. Remembered per device. */
export function useClarSize() {
  const [step, setStep] = useState<number | "auto">(() => {
    try {
      const v = localStorage.getItem(KEY);
      return v !== null && STEPS_VH[Number(v)] !== undefined ? Number(v) : "auto";
    } catch {
      return "auto";
    }
  });
  const lastPx = useRef(0); // what Auto last chose, so ¶− / ¶+ start from what's on screen
  const set = (s: number | "auto") => {
    setStep(s);
    try {
      localStorage.setItem(KEY, String(s));
    } catch {
      /* not persisted; fine */
    }
  };
  const from = () => {
    if (step !== "auto") return step;
    return nearestStep(lastPx.current);
  };
  const move = (d: number) => set(Math.max(0, Math.min(STEPS_VH.length - 1, from() + d)));
  return { step, lastPx, auto: () => set("auto"), smaller: () => move(-1), bigger: () => move(1), canSmaller: step === "auto" || step > 0, canBigger: step === "auto" || step < STEPS_VH.length - 1 };
}

/** ¶− / Auto / ¶+ (wireframe). Same button look as A− / A+. */
export function ClarSizeButtons({ z }: { z: ReturnType<typeof useClarSize> }) {
  return (
    <span className="zoom" role="group" aria-label="Clarification size">
      <button onClick={z.smaller} disabled={!z.canSmaller} aria-label="Clarifications: smaller">¶−</button>
      <button onClick={z.auto} aria-pressed={z.step === "auto"} className="auto">Auto</button>
      <button onClick={z.bigger} disabled={!z.canBigger} aria-label="Clarifications: bigger">¶+</button>
    </span>
  );
}

/** Projector clarifications, oldest first, in whatever space the timer leaves. */
export function FitList({ items, z }: { items: Item[]; z: ReturnType<typeof useClarSize> }) {
  const box = useRef<HTMLDivElement>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const again = () => setTick((n) => n + 1);
    window.addEventListener("resize", again);
    document.fonts?.ready.then(again); // math fonts load late and change the height
    return () => window.removeEventListener("resize", again);
  }, []);
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    if (z.step !== "auto") {
      el.style.fontSize = `${STEPS_VH[z.step]}vh`;
      return;
    }
    let lo = AUTO_MIN_PX;
    let hi = Math.max(AUTO_MIN_PX, (window.innerHeight * AUTO_MAX_VH) / 100);
    for (let i = 0; i < 10 && hi - lo > 1; i++) {
      const mid = (lo + hi) / 2;
      el.style.fontSize = `${mid}px`;
      if (el.scrollHeight > el.clientHeight + 1) hi = mid;
      else lo = mid;
    }
    // Largest size that fits, then three steps down (never bigger than what fits).
    const fit = Math.floor(lo);
    const px = Math.min(fit, Math.round((STEPS_VH[Math.max(0, nearestStep(fit) - AUTO_BACK_STEPS)] * window.innerHeight) / 100));
    el.style.fontSize = `${px}px`;
    z.lastPx.current = px;
  }, [items, z.step, tick]);
  return (
    <div className={`clars ${z.step === "auto" ? "" : "manual"}`} ref={box} aria-live="polite">
      <h2 className="clars-h">Clarifications</h2>
      {items.map((c) => (
        <ClarItem key={c.id} c={c} />
      ))}
    </div>
  );
}

/** Turn a Google Docs link into one that can be framed; anything else is used as given. */
export function docEmbedUrl(u: string): string {
  try {
    const x = new URL(u);
    if (x.hostname === "docs.google.com") {
      if (/\/pub\b/.test(x.pathname)) {
        x.searchParams.set("embedded", "true"); // "Publish to web" link
        return x.toString();
      }
      const m = x.pathname.match(/^\/document\/d\/([^/]+)/);
      if (m && m[1] !== "e") return `https://docs.google.com/document/d/${m[1]}/preview`; // "Anyone with the link"
    }
  } catch {
    /* not a URL: let the iframe show its own error */
  }
  return u;
}
