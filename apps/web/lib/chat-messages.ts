import type { UIMessage } from "ai"
import type { ConversationMessage } from "@/types/api"
import { INLINE_TURN_TOOL_NAME, splitConversationMessages } from "@/lib/ai-inline-turn-persistence"

/** Extract display text from live or persisted UI messages (parts + legacy content). */
export function uiMessageText(message: UIMessage): string {
  const parts = (message.parts ?? []) as Array<{ type?: string; text?: string }>
  const fromParts = parts
    .filter((part) => part.type === "text" && typeof part.text === "string")
    .map((part) => part.text as string)
    .join("")
  if (fromParts.trim()) return fromParts

  const legacy = (message as { content?: unknown }).content
  if (typeof legacy === "string") return legacy
  if (Array.isArray(legacy)) {
    return legacy
      .filter((part): part is { type?: string; text?: string } => typeof part === "object" && part !== null)
      .filter((part) => part.type === "text" && typeof part.text === "string")
      .map((part) => part.text as string)
      .join("")
  }
  return ""
}

/** True when assistant text is a tool/envelope JSON dump that belongs on chips. */
export function looksLikeToolJson(text: string | null | undefined): boolean {
  const raw = (text || "").trim()
  if (!raw || (raw[0] !== "{" && raw[0] !== "[")) return false
  try {
    const parsed = JSON.parse(raw) as unknown
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      const keys = parsed as Record<string, unknown>
      return ["success", "error_code", "error_detail", "tool_calls", "observation"].some(
        (key) => key in keys,
      )
    }
    if (Array.isArray(parsed) && parsed[0] && typeof parsed[0] === "object") {
      const first = parsed[0] as Record<string, unknown>
      return "output" in first || ("name" in first && ("input" in first || "output" in first))
    }
  } catch {
    return /"(success|error_code|error_detail|tool_calls)"/.test(raw.slice(0, 160))
  }
  return false
}

function toolCallsToParts(message: ConversationMessage): UIMessage["parts"] {
  const parts: UIMessage["parts"] = [{ type: "text", text: message.content }]
  if (!Array.isArray(message.tool_calls)) return parts

  for (const [index, entry] of message.tool_calls.entries()) {
    if (!entry || typeof entry !== "object") continue
    const row = entry as {
      name?: string
      displayName?: string
      input?: unknown
      output?: unknown
    }
    const toolName = row.name || "tool"
    if (toolName === INLINE_TURN_TOOL_NAME) continue
    parts.push({
      type: `tool-${toolName}`,
      toolCallId: `${message.id}-tool-${index}`,
      toolName,
      state: row.output !== undefined ? "output-available" : "input-available",
      output: row.output,
      input: row.input,
    } as UIMessage["parts"][number])
  }

  return parts
}

export type ChatUIMessageMetadata = {
  /** ISO timestamptz from conversation_messages.created_at (or provisional client stamp). */
  created_at?: string
}

export function conversationMessageToUI(message: ConversationMessage): UIMessage {
  const createdAt = (message.created_at || "").trim() || undefined
  return {
    id: message.id,
    role: message.role === "assistant" ? "assistant" : "user",
    parts: toolCallsToParts(message),
    metadata: createdAt ? ({ created_at: createdAt } satisfies ChatUIMessageMetadata) : undefined,
  }
}

export function conversationMessagesToUI(messages: ConversationMessage[]): UIMessage[] {
  const { chatMessages } = splitConversationMessages(messages)
  return chatMessages.map(conversationMessageToUI)
}
