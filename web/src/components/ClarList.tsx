import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import MarkdownIt from "markdown-it";
import mathPlugin from "@vscode/markdown-it-katex";
import "katex/dist/katex.min.css"; // bundled with its fonts: nothing is fetched from a CDN (invariant 6)
import type { Clar } from "../api";
import type { ClarSize } from "../displaySettings";

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

export const STEPS_VH = [2.5, 3.5, 4.5, 6, 8, 10, 12, 15]; // manual sizes, as % of screen height (CLAR_STEPS of them)
const AUTO_MAX_VH = 11; // Auto never goes bigger than this, so one short line isn't absurd
const AUTO_MIN_PX = 14;
const AUTO_BACK_STEPS = 3; // Auto lands where three ¶− clicks from the largest size that fits would (PM, 2026-10-02)
const AUTO_GUESS = 2; // where ¶−/¶+ start from Auto when this browser hasn't measured the projector

/** The manual step closest to a pixel size. */
const nearestStep = (px: number) => {
  const vh = (px / window.innerHeight) * 100;
  return STEPS_VH.reduce((best, v, i) => (Math.abs(v - vh) < Math.abs(STEPS_VH[best] - vh) ? i : best), 0);
};

// The step Auto picked on the projector. It depends on that screen, so it stays in this browser
// (not the room): the proctor page reads it when the display window runs in the same browser.
const AUTO_KEY = "clarsize:auto";
const readAuto = (): number | null => {
  try {
    const v = Number(localStorage.getItem(AUTO_KEY) ?? NaN);
    return STEPS_VH[v] !== undefined ? v : null;
  } catch {
    return null;
  }
};

/** The step Auto shows on this browser's projector window, if it has one. */
export function useMeasuredAuto() {
  const [step, setStep] = useState(readAuto);
  useEffect(() => {
    const sync = (e: StorageEvent) => e.key === AUTO_KEY && setStep(readAuto());
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);
  return step;
}

/** One ¶− / ¶+ click from `size`. From Auto, start from what Auto shows (or a guess). */
export function stepClar(size: ClarSize, d: -1 | 1, measured: number | null): ClarSize {
  const from = size === "auto" ? (measured ?? AUTO_GUESS) : size;
  return Math.max(0, Math.min(STEPS_VH.length - 1, from + d));
}

/** "3 of 8"; Auto shows the size it picked when we know it. */
export const clarLabel = (size: ClarSize, measured: number | null) => {
  const i = size === "auto" ? measured : size;
  return i === null ? "Auto" : `${i + 1} of ${STEPS_VH.length}`;
};

/** ¶− / size / ¶+ / Auto (wireframe), on the proctor page. Same button look as A− / A+. */
export function ClarSizeButtons({ size, onChange }: { size: ClarSize; onChange: (s: ClarSize) => void }) {
  const measured = useMeasuredAuto();
  return (
    <span className="zoom" role="group" aria-label="Clarification size">
      <button onClick={() => onChange(stepClar(size, -1, measured))} disabled={size === 0} aria-label="Clarifications: smaller">¶−</button>
      <output className="size" aria-label="Clarification size now">{clarLabel(size, measured)}</output>
      <button onClick={() => onChange(stepClar(size, 1, measured))} disabled={size === STEPS_VH.length - 1} aria-label="Clarifications: bigger">¶+</button>
      <button onClick={() => onChange("auto")} aria-pressed={size === "auto"} className="auto">Auto</button>
    </span>
  );
}

/** Projector clarifications, oldest first, in whatever space the timer leaves. */
export function FitList({ items, size }: { items: Item[]; size: ClarSize }) {
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
    if (size !== "auto") {
      el.style.fontSize = `${STEPS_VH[size]}vh`;
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
    try {
      localStorage.setItem(AUTO_KEY, String(nearestStep(px)));
    } catch {
      /* the proctor page then steps from a guess */
    }
  }, [items, size, tick]);
  return (
    <div className={`clars ${size === "auto" ? "" : "manual"}`} ref={box} aria-live="polite">
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
