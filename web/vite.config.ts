import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// `npm run dev`: proxies /api to a local uvicorn on :8000. Secure cookies work on localhost.
// `npm test`: Vitest in a fake browser (jsdom); setup in src/test/setup.ts.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000" } },
  test: { environment: "jsdom", setupFiles: ["src/test/setup.ts"] },
});
