/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/next/",
  server: {
    proxy: {
      "/api": { target: "http://127.0.0.1:8799", ws: true },
      "/static": "http://127.0.0.1:8799",
      // Serve the authenticated production build from the local dashboard.
      "/next": "http://127.0.0.1:8799",
    },
  },
  build: {
    outDir: "../plugins/fullstack-agents/scripts/lib/dashboard-react",
    emptyOutDir: true,
    cssCodeSplit: false,
    modulePreload: false,
    rollupOptions: {
      output: { entryFileNames: "app.js", chunkFileNames: "app-[name].js", assetFileNames: "app.[ext]" },
    },
  },
  test: { environment: "jsdom", include: ["src/**/*.test.ts", "src/**/*.test.tsx"] },
});
