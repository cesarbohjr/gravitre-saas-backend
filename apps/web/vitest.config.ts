import { defineConfig } from "vitest/config"
import path from "node:path"

export default defineConfig({
  test: {
    environment: "node",
    // `.tsx` was missing, so every component test in __tests__ was collected by
    // nobody and silently reported nothing -- knowledge-citation-card.test.tsx had
    // never run once. A test that cannot fail is worse than no test.
    include: ["__tests__/**/*.test.{ts,tsx}"],
    setupFiles: ["./__tests__/setup.ts"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
})
