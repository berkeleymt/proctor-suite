import { configDefaults, defineWorkspace } from "vitest/config";

// `npm test` runs both projects. Each can run alone: `npm run test:unit`, `npm run test:layout`.
// - unit: fast, in a fake browser (jsdom). Rules, text, what clicks do.
// - layout: real Chromium (headless, via Playwright), for things jsdom can't see: sizes and
//   positions. Files named *.browser.test.tsx. First time: `npx playwright install chromium`.
export default defineWorkspace([
  {
    extends: "./vite.config.ts",
    test: { name: "unit", environment: "jsdom", exclude: [...configDefaults.exclude, "src/**/*.browser.test.*"] },
  },
  {
    extends: "./vite.config.ts",
    test: {
      name: "layout",
      include: ["src/**/*.browser.test.*"],
      browser: { enabled: true, provider: "playwright", name: "chromium", headless: true, viewport: { width: 1280, height: 800 }, screenshotFailures: false },
    },
  },
]);
