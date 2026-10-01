import { useEffect, useLayoutEffect, useRef, useState } from "react";

const STEPS = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1];
const DEFAULT = 0.8;

/** Persisted zoom level (index into STEPS) per surface. 1 = the largest size that still fits. */
export function useZoom(key: string) {
  const [i, setI] = useState(() => {
    try {
      const v = Number(localStorage.getItem(`zoom:${key}`));
      return STEPS.includes(v) ? STEPS.indexOf(v) : STEPS.indexOf(DEFAULT);
    } catch {
      return STEPS.indexOf(DEFAULT);
    }
  });
  const set = (n: number) => {
    const j = Math.max(0, Math.min(STEPS.length - 1, n));
    setI(j);
    try {
      localStorage.setItem(`zoom:${key}`, String(STEPS[j]));
    } catch {
      /* storage may be unavailable; zoom just won't persist */
    }
  };
  return { zoom: STEPS[i], smaller: () => set(i - 1), bigger: () => set(i + 1), canSmaller: i > 0, canBigger: i < STEPS.length - 1 };
}

/** A− / A+ buttons. */
export function ZoomButtons({ z, label = "Timer size" }: { z: ReturnType<typeof useZoom>; label?: string }) {
  return (
    <span className="zoom" role="group" aria-label={label}>
      <button onClick={z.smaller} disabled={!z.canSmaller} aria-label={`${label}: smaller`}>
        A−
      </button>
      <button onClick={z.bigger} disabled={!z.canBigger} aria-label={`${label}: bigger`}>
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

/** True while the pointer/keyboard/touch was active in the last `ms`; used to fade controls. */
export function useActive(ms = 4000) {
  const [on, setOn] = useState(true);
  useEffect(() => {
    let t: number;
    const wake = () => {
      setOn(true);
      clearTimeout(t);
      t = window.setTimeout(() => setOn(false), ms);
    };
    wake();
    const ev = ["pointermove", "pointerdown", "keydown"] as const;
    ev.forEach((e) => window.addEventListener(e, wake));
    return () => {
      clearTimeout(t);
      ev.forEach((e) => window.removeEventListener(e, wake));
    };
  }, [ms]);
  return on;
}
