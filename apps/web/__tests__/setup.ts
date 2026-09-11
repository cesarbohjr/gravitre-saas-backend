/**
 * Node 20 has no global `WebSocket` (it landed unflagged in Node 22), and
 * @supabase/realtime-js throws "Node.js detected but native WebSocket not found"
 * at import time when it is absent.
 *
 * `ws` must be a *declared* devDependency. A pnpm override alone only pins a
 * nested copy; CI's isolated node_modules will not resolve `import "ws"` from
 * this file. That is why this setup turned the whole Vitest job red.
 */
import { WebSocket } from "ws"

if (typeof globalThis.WebSocket === "undefined") {
  ;(globalThis as { WebSocket?: unknown }).WebSocket = WebSocket
}

/** jsdom has no ResizeObserver; Radix size/focus hooks throw without this. */
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}
