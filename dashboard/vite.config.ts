/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/next/",
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
