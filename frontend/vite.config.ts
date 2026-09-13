import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Client-side SPA only — no SSR, no Next.js. The backend (FastAPI) is the
// only server; this dev server just serves static assets + HMR.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
