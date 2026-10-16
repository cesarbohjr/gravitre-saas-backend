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
    // Use forks pool (single sequential fork) instead of the default threads pool.
    // The threads pool shares a single worker_threads-based pool across all test
    // files; under certain combinations of mocked globals the pool can deadlock
    // and hang indefinitely. A single-fork process runs every test in the same
    // OS process sequentially — no inter-worker shared state — which eliminates
    // the cross-file interference while keeping total runtime under 40 s.
    pool: "forks",
    poolOptions: {
      forks: {
        singleFork: true,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
})
