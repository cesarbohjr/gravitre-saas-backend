import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { resolve } from "node:path"

/**
 * Visual-review harness only, not part of the shipped extension.
 *
 * The screenshot browser runs in a separate sandbox and can only reach the web
 * app's dev server on :3000, so the harness is built as static assets into
 * apps/web/public/ext-harness and reviewed from there. Delete that output (and
 * this config) once review is done.
 */
export default defineConfig({
  root: __dirname,
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": resolve(__dirname, "src") } },
  base: "/e2e/ext-harness/",
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  build: {
    outDir: resolve(__dirname, "../web/public/e2e/ext-harness"),
    emptyOutDir: true,
    rollupOptions: { input: resolve(__dirname, "preview.html") },
  },
})
