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

/** Same message by content, for two copies that carry different ids. */
function sameMessage(a: UIMessage, b: UIMessage): boolean {
  return a.role === b.role && normalizeUiText(a) === normalizeUiText(b)
}

/**
 * How many messages at the head of `appended` re-describe the tail of `stored`.
 *
 * Returns the longest such run, so a whole duplicated turn collapses rather than
 * only its first message.
 */
function trailingOverlapLength(stored: UIMessage[], appended: UIMessage[]): number {
  const limit = Math.min(stored.length, appended.length)
  for (let run = limit; run > 0; run -= 1) {
    let matches = true
    for (let offset = 0; offset < run; offset += 1) {
      if (!sameMessage(stored[stored.length - run + offset], appended[offset])) {
        matches = false
        break
      }
    }
    if (matches) return run
  }
  return 0
}

/**
 * Combine server-stored messages with the client's live ones.
 *
 * Id matching alone is not enough, and never was: live ids are generated on the
 * client while stored ids are database uuids, so the same turn appears under two
 * different ids and every id-based check misses it. Stored `[user, assistant]`
 * plus live `[user, assistant]` therefore rendered as user, assistant, user,
 * assistant — the doubling reported from a live screenshot.
 *
 * This was already known for the user message: the previous implementation
 * dropped a duplicated leading live *user* prompt by comparing text. The bug was
 * that the same comparison stopped there, so the assistant reply behind it still
 * duplicated. This applies that existing rule to the whole overlapping run
 * instead of just the first message.
 *
 * Stored wins on a match because it is the persisted copy. One case this does
 * not catch: a live assistant message still mid-stream whose text is a partial
 * prefix of the stored row will not compare equal, so it can still duplicate.
 * Matching on prefixes would risk collapsing genuinely distinct replies, so it
 * is deliberately left alone.
 */
export function mergeTranscriptWithLiveMessages(
  storedTranscript: UIMessage[],
  liveMessages: UIMessage[],
): UIMessage[] {
  if (liveMessages.length === 0) return storedTranscript
  if (storedTranscript.length === 0) return liveMessages

  const storedIds = new Set(storedTranscript.map((message) => message.id))
  const appended = liveMessages.filter((message) => !storedIds.has(message.id))
  if (appended.length === 0) return storedTranscript

  const overlap = trailingOverlapLength(storedTranscript, appended)
  if (overlap === 0) return [...storedTranscript, ...appended]
  return [...storedTranscript, ...appended.slice(overlap)]
}

function normalizeUiText(message: UIMessage): string {
  return uiMessageText(message).trim()
}
