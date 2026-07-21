import type { UIMessage } from "ai"
import type { ConversationMessage } from "@/types/api"
import { conversationMessageToUI, uiMessageText } from "@/lib/chat-messages"
import { splitConversationMessages } from "@/lib/ai-inline-turn-persistence"

function stableMessageId(message: ConversationMessage, index: number): string {
  const existing = (message.id || "").trim()
  if (existing) return existing
  return `${message.role}-${message.created_at || index}-${index}`
}

function withStableId(message: ConversationMessage, index: number): ConversationMessage {
  return { ...message, id: stableMessageId(message, index) }
}

function syntheticUserMessage(
  text: string,
  anchorId: string,
  createdAt?: string | null,
): UIMessage {
  const iso = (createdAt || "").trim() || undefined
  return {
    id: `user-inferred-${anchorId}`,
    role: "user",
    parts: [{ type: "text", text }],
    metadata: iso ? { created_at: iso } : undefined,
  }
}

/**
 * Build a reliable chat transcript from stored messages.
 * Repairs missing user bubbles (common when ids collide or legacy rows omit user rows).
 */
export function buildConversationTranscript(
  stored: ConversationMessage[],
  options?: { conversationTitle?: string | null },
): UIMessage[] {
  const { chatMessages } = splitConversationMessages(stored)
  if (chatMessages.length === 0) return []

  const normalized = chatMessages.map(withStableId)
  const transcript: UIMessage[] = []
  const titleFallback =
    options?.conversationTitle && options.conversationTitle !== "Gravitre AI"
      ? options.conversationTitle.trim()
      : ""

  for (let index = 0; index < normalized.length; index += 1) {
    const row = normalized[index]
    const ui = conversationMessageToUI(row)

    if (row.role === "assistant") {
      const previous = transcript[transcript.length - 1]
      if (!previous || previous.role !== "user") {
        const priorUser = row.role === "assistant" ? normalized[index - 1] : null
        if (priorUser?.role === "user" && priorUser.content.trim()) {
          transcript.push(conversationMessageToUI(priorUser))
        } else if (titleFallback && transcript.length === 0) {
          transcript.push(syntheticUserMessage(titleFallback, ui.id, row.created_at))
        }
      }
    }

    if (transcript.some((entry) => entry.id === ui.id)) continue
    transcript.push(ui)
  }

  return transcript
}

export function mergeTranscriptWithLiveMessages(
  storedTranscript: UIMessage[],
  liveMessages: UIMessage[],
): UIMessage[] {
  if (liveMessages.length === 0) return storedTranscript
  if (storedTranscript.length === 0) return liveMessages

  const storedIds = new Set(storedTranscript.map((message) => message.id))
  const appended = liveMessages.filter((message) => !storedIds.has(message.id))
  if (appended.length === 0) return storedTranscript

  const lastStored = storedTranscript[storedTranscript.length - 1]
  const firstLive = appended[0]
  if (
    lastStored?.role === "user" &&
    firstLive?.role === "user" &&
    normalizeUiText(lastStored) === normalizeUiText(firstLive)
  ) {
    return [...storedTranscript, ...appended.slice(1)]
  }

  return [...storedTranscript, ...appended]
}

function normalizeUiText(message: UIMessage): string {
  return uiMessageText(message).trim()
}
