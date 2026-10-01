import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// `npm run dev`: proxies /api to a local uvicorn on :8000. Secure cookies work on localhost.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000" } },
});
