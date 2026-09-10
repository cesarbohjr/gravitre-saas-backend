/**
 * Node 20 has no global `WebSocket` (it landed unflagged in Node 22), and
 * @supabase/realtime-js throws "Node.js detected but native WebSocket not found"
 * at import time when it is absent. That failure has been sitting in the suite as
 * a permanently-red file, which trains everyone to read red as normal.
 *
 * The `ws` package is already a dependency and is what Supabase would use itself,
 * so pointing the global at it fixes the cause rather than skipping the file.
 */
import { WebSocket } from "ws"

if (typeof globalThis.WebSocket === "undefined") {
  ;(globalThis as { WebSocket?: unknown }).WebSocket = WebSocket
}
