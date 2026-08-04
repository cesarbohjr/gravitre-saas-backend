import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { resolve } from "node:path"

/**
 * Builds the visual harness (preview.html) as a standalone static bundle.
 *
 * Why this exists separately from vite.config.ts: the extension's own dev
 * server only ever binds to this machine's loopback, and the only port routed
 * out to a browser is the web app's. Emitting the harness as plain static
 * files lets it be dropped into `apps/web/public/<dir>` and reviewed in a real
 * browser at a real URL.
 *
 * Nothing here is part of the shipped extension — `preview.html` and
 * `src/preview/*` are excluded from both extension builds.
 */
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": resolve(__dirname, "src") },
  },
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  // Relative asset URLs, so the bundle works under whatever subdirectory it is
  // served from without being rebuilt.
  base: "./",
  build: {
    outDir: resolve(__dirname, "dist-preview"),
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      input: { preview: resolve(__dirname, "preview.html") },
    },
  },
})
