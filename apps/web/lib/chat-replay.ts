import { apiFetch } from "@/lib/fetcher"
import { conversationMessageToUI, looksLikeToolJson, uiMessageText } from "@/lib/chat-messages"
import type { ConversationMessage } from "@/types/api"
import type { UIMessage } from "ai"

export type ChatReplayPayload = {
  ok: boolean
  already_have?: boolean
  event_id?: string
  conversation_id?: string
  user_text?: string
  assistant_text?: string
  assistant_message_id?: string
  tool_calls?: unknown[]
}

const lastEventStorageKey = (conversationId: string) => `gravitre.chat.last-event.${conversationId}`

export function readLastEventId(conversationId: string | null | undefined): string | null {
  if (!conversationId || typeof window === "undefined") return null
  try {
    return window.sessionStorage.getItem(lastEventStorageKey(conversationId))
  } catch {
    return null
  }
}

export function writeLastEventId(conversationId: string | null | undefined, eventId: string | null | undefined): void {
  if (!conversationId || !eventId || typeof window === "undefined") return
  try {
    window.sessionStorage.setItem(lastEventStorageKey(conversationId), eventId)
  } catch {
    // ignore quota
  }
}

export function isUserChatAbort(error: unknown): boolean {
  const raw = error instanceof Error ? `${error.name} ${error.message}` : String(error || "")
  return /abort|aborterror|stopped by user|the user aborted/i.test(raw)
}

export async function fetchCompletedChatReplay(
  conversationId: string | null | undefined,
): Promise<ChatReplayPayload | null> {
  const id = conversationId?.trim()
  if (!id) return null
  const lastEventId = readLastEventId(id)
  try {
    const response = await apiFetch(`/api/chat/replay?conversation_id=${encodeURIComponent(id)}`, {
      method: "GET",
      headers: lastEventId ? { "Last-Event-ID": lastEventId } : undefined,
      timeoutMs: 8_000,
    })
    if (!response.ok) return null
    const body = (await response.json()) as ChatReplayPayload
    if (!body?.ok) return null
    return body
  } catch {
    return null
  }
}

export function applyChatReplay(messages: UIMessage[], replay: ChatReplayPayload): UIMessage[] {
  if (replay.already_have) return messages
  const text = (replay.assistant_text || "").trim()
  if (!text || looksLikeToolJson(text)) return messages
  const last = messages[messages.length - 1]
  if (last?.role === "assistant" && uiMessageText(last).trim()) return messages
  const assistant = conversationMessageToUI({
    id: replay.assistant_message_id || replay.event_id || `replay-${Date.now()}`,
    conversation_id: replay.conversation_id || "",
    role: "assistant",
    content: text,
    tool_calls: Array.isArray(replay.tool_calls) ? replay.tool_calls : undefined,
    created_at: new Date().toISOString(),
  } satisfies ConversationMessage)
  if (replay.event_id) writeLastEventId(replay.conversation_id, replay.event_id)
  if (last?.role === "assistant") return [...messages.slice(0, -1), assistant]
  return [...messages, assistant]
}

export async function recoverCompletedChatTurn(
  conversationId: string | null | undefined,
  messages: UIMessage[],
): Promise<UIMessage[] | null> {
  const replay = await fetchCompletedChatReplay(conversationId)
  if (!replay) return null
  const next = applyChatReplay(messages, replay)
  if (next === messages) return null
  return next
}
