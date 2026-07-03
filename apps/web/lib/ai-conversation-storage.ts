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
