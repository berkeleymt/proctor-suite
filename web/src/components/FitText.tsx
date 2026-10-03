import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { TIMER_PCTS, type TimerPct } from "../displaySettings";

/** A− / size / A+ for the projector timer, on the proctor page. */
export function TimerSizeButtons({ pct, onChange }: { pct: TimerPct; onChange: (p: TimerPct) => void }) {
  const i = TIMER_PCTS.indexOf(pct);
  const label = "Display timer size";
  return (
    <span className="zoom" role="group" aria-label={label}>
      <button onClick={() => onChange(TIMER_PCTS[i - 1])} disabled={i <= 0} aria-label={`${label}: smaller`}>
        A−
      </button>
      <output className="size" aria-label={`${label} now`}>{pct}%</output>
      <button onClick={() => onChange(TIMER_PCTS[i + 1])} disabled={i >= TIMER_PCTS.length - 1} aria-label={`${label}: bigger`}>
        A+
      </button>
    </span>
  );
}

/**
 * Text that always fits its box: measures the text at a reference size, then scales so both width
 * and height fit, times `zoom` (max 1). Re-fits on container resize, zoom, and text length change.
 */
export function FitText({ text, zoom, className = "" }: { text: string; zoom: number; className?: string }) {
  const box = useRef<HTMLDivElement>(null);
  const span = useRef<HTMLSpanElement>(null);
  const [size, setSize] = useState(48);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!box.current) return;
    const ro = new ResizeObserver(() => setTick((n) => n + 1));
    ro.observe(box.current);
    return () => ro.disconnect();
  }, []);

  useLayoutEffect(() => {
    const b = box.current;
    const s = span.current;
    if (!b || !s) return;
    const REF = 100;
    s.style.fontSize = `${REF}px`;
    const w = s.offsetWidth || 1;
    const h = s.offsetHeight || 1;
    const fit = Math.min(b.clientWidth / w, b.clientHeight / h) * REF;
    setSize(Math.max(8, Math.floor(fit * zoom * 0.96)));
  }, [text.length, zoom, tick]);

  return (
    <div className={`fit ${className}`} ref={box}>
      <span ref={span} style={{ fontSize: size }}>
        {text}
      </span>
    </div>
  );
}
