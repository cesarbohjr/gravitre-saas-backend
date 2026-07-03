// Handoff bridge for the unified "Gravitre AI" front door.
//
// `/ai` now runs execute, chat, and find inline. SessionStorage handoffs remain
import { APP_ROUTES } from "@/lib/app-routes"

// for deep links into Command Center, Workspace Chat, and Universal Search when those pages
// are opened directly.

export type AiEngine = "execute" | "chat" | "find"

export type AiHandoff = {
  prompt: string
  autoRun: boolean
  /** Where the routing decision came from, for optional UI hinting. */
  source?: "model" | "heuristic" | "manual"
  /** Epoch ms — used to ignore stale handoffs. */
  ts: number
}

const STORAGE_PREFIX = "gravitre-ai-handoff:"
// Handoffs older than this are ignored (e.g. a stale tab reopened later).
const MAX_AGE_MS = 60_000

export const AI_ENGINE_ROUTES: Record<AiEngine, string> = {
  execute: APP_ROUTES.gravitreAi,
  chat: "/assistant",
  find: "/search",
}

function keyFor(engine: AiEngine): string {
  return `${STORAGE_PREFIX}${engine}`
}

/** Store a pending prompt for an engine before navigating to it. */
export function setAiHandoff(engine: AiEngine, handoff: Omit<AiHandoff, "ts">): void {
  if (typeof window === "undefined") return
  try {
    const payload: AiHandoff = { ...handoff, ts: Date.now() }
    window.sessionStorage.setItem(keyFor(engine), JSON.stringify(payload))
  } catch {
    // sessionStorage may be unavailable (private mode); non-fatal.
  }
}

/**
 * Read and clear the pending prompt for an engine. Returns null when there is
 * no fresh handoff. Safe to call on every mount.
 */
export function consumeAiHandoff(engine: AiEngine): AiHandoff | null {
  if (typeof window === "undefined") return null
  try {
    const raw = window.sessionStorage.getItem(keyFor(engine))
    if (!raw) return null
    window.sessionStorage.removeItem(keyFor(engine))
    const parsed = JSON.parse(raw) as AiHandoff
    if (!parsed?.prompt || typeof parsed.ts !== "number") return null
    if (Date.now() - parsed.ts > MAX_AGE_MS) return null
    return parsed
  } catch {
    return null
  }
}
