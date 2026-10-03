import type { ReactNode } from "react";

/**
 * One button in an action bar. A button that can't run right now stays in place, greyed out
 * (aria-disabled, so it can still be clicked or focused to learn why), instead of disappearing.
 */
export type Act = {
  key: string;
  label: string;
  /** Every label this slot can ever show. The slot is as wide as the longest, so it never resizes. */
  labels?: readonly string[];
  tone?: "primary" | "danger";
  /** Empty = can run. Otherwise the plain-language reason it can't, shown when clicked. */
  why: string;
  run: (e: React.MouseEvent) => void;
};

/**
 * Text that always takes the room of its longest possible value: every value sits in the same
 * grid cell and all but the current one are invisible. Works with any font, no measuring.
 */
export function Sized({ text, all }: { text: string; all: readonly string[] }) {
  return (
    <span className="sized">
      <span>{text}</span>
      {all.map((t) => (
        <span key={t} aria-hidden="true">
          {t}
        </span>
      ))}
    </span>
  );
}

/**
 * Buttons in fixed groups. The admin rows and the floating bulk bar both use this, so they look
 * and behave alike; the look lives in the `.acts` tokens in styles.css.
 */
export function ActionBar({ label, groups, onBlocked }: { label: string; groups: Act[][]; onBlocked: (why: string) => void }): ReactNode {
  return (
    <span className="acts" role="group" aria-label={label}>
      {groups.map((g, i) => (
        <span className="acts-group" key={i}>
          {g.map((a) => (
            <button
              key={a.key}
              type="button"
              className="act"
              data-slot={a.key}
              data-tone={a.tone}
              aria-disabled={a.why ? "true" : undefined}
              title={a.why || undefined}
              onClick={(e) => (a.why ? onBlocked(a.why) : a.run(e))}
            >
              {a.labels ? <Sized text={a.label} all={a.labels} /> : a.label}
            </button>
          ))}
        </span>
      ))}
    </span>
  );
}
