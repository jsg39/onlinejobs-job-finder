import { readFile } from "node:fs/promises";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

// Serves the newest triage run (../out/latest.json) at /latest.json, re-read on every request.
const latestRun = (): Plugin => ({
  name: "latest-run",
  configureServer(server) {
    server.middlewares.use("/latest.json", async (_req, res) => {
      try {
        const body = await readFile(new URL("../out/latest.json", import.meta.url));
        res.setHeader("Content-Type", "application/json");
        res.end(body);
      } catch {
        res.statusCode = 404;
        res.end(JSON.stringify({ error: "No run yet. Run: python -m ojagent.triage" }));
      }
    });
  },
});

export default defineConfig({ plugins: [react(), latestRun()] });
