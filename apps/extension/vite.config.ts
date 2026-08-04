import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { resolve } from "node:path"

/**
 * Two separate builds share this config, selected by `mode`:
 *
 * - `content` emits ONE self-contained IIFE. Content scripts are injected into
 *   someone else's page, so they cannot rely on ESM imports or code-splitting
 *   at runtime. Its CSS is imported with `?inline` and pushed into a shadow
 *   root by the entry itself, so nothing is ever added to the host document.
 * - the default build emits the extension-owned pages (popup, side panel) and
 *   the service worker, which are ordinary ES modules.
 */
export default defineConfig(({ mode }) => {
  const isContent = mode === "content"

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: { "@": resolve(__dirname, "src") },
    },
    define: {
      // React reads this; without it the dev build ships warnings into a
      // customer's page.
      "process.env.NODE_ENV": JSON.stringify("production"),
    },
    build: {
      outDir: "dist",
      emptyOutDir: !isContent,
      minify: "esbuild",
      target: "chrome116",
      cssCodeSplit: false,
      ...(isContent
        ? {
            lib: {
              entry: resolve(__dirname, "src/content/index.tsx"),
              name: "GravitreOverlay",
              formats: ["iife" as const],
              fileName: () => "content/overlay.js",
            },
          }
        : {
            rollupOptions: {
              input: {
                popup: resolve(__dirname, "popup.html"),
                sidepanel: resolve(__dirname, "sidepanel.html"),
                background: resolve(__dirname, "src/background/index.ts"),
              },
              output: {
                entryFileNames: (chunk) =>
                  chunk.name === "background" ? "background.js" : "assets/[name].js",
                chunkFileNames: "assets/[name].js",
                assetFileNames: "assets/[name][extname]",
              },
            },
          }),
    },
  }
})
