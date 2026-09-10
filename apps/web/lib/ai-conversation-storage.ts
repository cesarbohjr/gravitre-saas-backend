import type { UIMessage } from "ai"

/** Active thread id for the unified Gravitre AI workspace (/ai). */
export const AI_CONVERSATION_ID_KEY = "gravitre_ai_conversation_id"

/** Legacy keys from older Workspace Chat (/assistant) — read for migration only. */
const LEGACY_CONVERSATION_ID_KEYS = ["gravitre_last_conversation_id"] as const

const messagesCacheKey = (conversationId: string) => `gravitre_ai_messages_${conversationId}`
const inlineTurnsCacheKey = (conversationId: string) => `gravitre_ai_inline_${conversationId}`

export function readStoredConversationId(): string | null {
  if (typeof window === "undefined") return null
  const current = localStorage.getItem(AI_CONVERSATION_ID_KEY)
  if (current) return current
  for (const legacyKey of LEGACY_CONVERSATION_ID_KEYS) {
    const legacy = localStorage.getItem(legacyKey)
    if (legacy) {
      localStorage.setItem(AI_CONVERSATION_ID_KEY, legacy)
      localStorage.removeItem(legacyKey)
      return legacy
    }
  }
  return null
}

export function writeStoredConversationId(conversationId: string | null): void {
  if (typeof window === "undefined") return
  if (conversationId) {
    localStorage.setItem(AI_CONVERSATION_ID_KEY, conversationId)
    for (const legacyKey of LEGACY_CONVERSATION_ID_KEYS) {
      localStorage.removeItem(legacyKey)
    }
    return
  }
  localStorage.removeItem(AI_CONVERSATION_ID_KEY)
  for (const legacyKey of LEGACY_CONVERSATION_ID_KEYS) {
    localStorage.removeItem(legacyKey)
  }
}

export function readCachedConversationMessages(conversationId: string): UIMessage[] | null {
  if (typeof window === "undefined") return null
  try {
    const raw = sessionStorage.getItem(messagesCacheKey(conversationId))
    if (!raw) return null
    const parsed = JSON.parse(raw) as UIMessage[]
    return Array.isArray(parsed) ? parsed : null
  } catch {
    return null
  }
}

export function writeCachedConversationMessages(conversationId: string, messages: UIMessage[]): void {
  if (typeof window === "undefined" || messages.length === 0) return
  try {
    sessionStorage.setItem(messagesCacheKey(conversationId), JSON.stringify(messages.slice(-80)))
  } catch {
    // sessionStorage may be unavailable
  }
}

export function clearCachedConversationMessages(conversationId: string): void {
  if (typeof window === "undefined") return
  sessionStorage.removeItem(messagesCacheKey(conversationId))
  sessionStorage.removeItem(inlineTurnsCacheKey(conversationId))
}

/**
 * Prefixes that hold private conversation content, as opposed to presentation
 * preferences. Anything listed here must not survive a logout.
 */
const PRIVATE_KEY_PREFIXES = [
  "gravitre_ai_messages_",
  "gravitre_ai_inline_",
  // Carries a prompt the user typed on one surface to be replayed on another.
  "gravitre-ai-handoff:",
] as const

/**
 * Erase every trace of the previous user's conversation from browser storage.
 *
 * Unmounting the assistant on logout removes it from the DOM, which is not the
 * same as removing it from the machine: the active thread id lives in
 * localStorage (so it outlives the tab entirely) and up to 80 cached messages
 * plus inline turns live in sessionStorage. Without this, logging out left the
 * previous user's conversation readable by whoever sat down next.
 *
 * Scans by prefix rather than clearing the single active id, because caches
 * accumulate one entry per conversation the user visited, and on logout we no
 * longer know which ids those were.
 *
 * Deliberately does not touch presentation preferences (chat canvas background,
 * float geometry). Those carry no conversation content, and clearing them would
 * be unrelated churn.
 */
export function purgeStoredConversationState(): void {
  if (typeof window === "undefined") return
  writeStoredConversationId(null)
  for (const store of [window.sessionStorage, window.localStorage]) {
    try {
      // Snapshot the key list first — removing while iterating by index skips keys.
      const keys: string[] = []
      for (let i = 0; i < store.length; i += 1) {
        const key = store.key(i)
        if (key && PRIVATE_KEY_PREFIXES.some((prefix) => key.startsWith(prefix))) keys.push(key)
      }
      for (const key of keys) store.removeItem(key)
    } catch {
      // Storage can be unavailable (private mode, quota, disabled cookies).
    }
  }
}

export function readCachedInlineTurns<T>(conversationId: string): T[] | null {
  if (typeof window === "undefined") return null
  try {
    const raw = sessionStorage.getItem(inlineTurnsCacheKey(conversationId))
    if (!raw) return null
    const parsed = JSON.parse(raw) as T[]
    return Array.isArray(parsed) ? parsed : null
  } catch {
    return null
  }
}

export function writeCachedInlineTurns<T>(conversationId: string, turns: T[]): void {
  if (typeof window === "undefined") return
  try {
    if (turns.length === 0) {
      sessionStorage.removeItem(inlineTurnsCacheKey(conversationId))
      return
    }
    sessionStorage.setItem(inlineTurnsCacheKey(conversationId), JSON.stringify(turns.slice(-20)))
  } catch {
    // sessionStorage may be unavailable
  }
}
