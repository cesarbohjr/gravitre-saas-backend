import { ApiError } from "@/lib/fetcher"

export type MissingConversationCheckInput = {
  orgReady: boolean
  activeConversationId: string | null
  conversationsLoading: boolean
  hasConversationInList: boolean
  hasPendingConversation: boolean
  isSessionBusy: boolean
  chatStatus: "ready" | "submitted" | "streaming" | "error"
}

/**
 * Sidebar pagination/search results are not an authoritative signal that the
 * active thread is gone. We only run a direct verification request when the
 * list is loaded, the active id is absent, and chat is idle.
 */
export function shouldVerifyMissingConversation(input: MissingConversationCheckInput): boolean {
  if (!input.orgReady || !input.activeConversationId || input.conversationsLoading) {
    return false
  }
  if (input.hasConversationInList) return false
  if (input.hasPendingConversation) return false
  if (input.isSessionBusy) return false
  if (input.chatStatus === "submitted" || input.chatStatus === "streaming") return false
  return true
}

/**
 * Only treat authorization/not-found responses as definitive "thread is gone".
 * Transient network/service failures should not wipe local chat state.
 */
export function isAuthoritativeMissingConversationError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 403 || error.status === 404)
}
