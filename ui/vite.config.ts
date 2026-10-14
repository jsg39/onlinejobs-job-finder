import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The FastAPI backend (uvicorn ojagent.api:app --port 8000) serves /api.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://127.0.0.1:8000" },
    // Native file events were being missed on Windows, leaving stale modules in the browser.
    watch: { usePolling: true, interval: 300 },
  },
});
