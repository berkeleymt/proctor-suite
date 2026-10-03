import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// jsdom has no layout: FitText only needs ResizeObserver to exist.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

afterEach(() => {
  cleanup();
  localStorage.clear();
});
