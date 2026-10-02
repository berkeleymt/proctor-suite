import { useEffect, useState } from "react";

/** The Proctor page opens the projector display in a window with this name. */
export const DISPLAY_WINDOW = "proctor-display";
export const isDisplayWindow = () => window.name === DISPLAY_WINDOW;

/** Ask for full screen; false if the browser says no (it wants a click inside this window first). */
export async function enterFullscreen(): Promise<boolean> {
  if (document.fullscreenElement) return true;
  try {
    await document.documentElement.requestFullscreen();
    return true;
  } catch {
    return false;
  }
}

/**
 * Full screen for the projector window as soon as it opens. Browsers only allow it right after a
 * click *in that window*, which a freshly opened popup doesn't have yet, so if the first try is
 * refused the next click or key press does it. `waiting` is true while we're waiting for that.
 */
export function useAutoFullscreen(on: boolean): boolean {
  const [waiting, setWaiting] = useState(false);
  useEffect(() => {
    if (!on || document.fullscreenElement) return;
    const events = ["pointerdown", "keydown"] as const;
    let stop = false;
    const enter = () => {
      enterFullscreen().then((ok) => {
        if (!ok) return;
        cleanup();
      });
    };
    const cleanup = () => {
      events.forEach((e) => window.removeEventListener(e, enter));
      setWaiting(false);
    };
    enterFullscreen().then((ok) => {
      if (ok || stop) return;
      events.forEach((e) => window.addEventListener(e, enter));
      setWaiting(true);
    });
    return () => {
      stop = true;
      cleanup();
    };
  }, [on]);
  return waiting;
}
