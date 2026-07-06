import type { UIMessage } from "ai"
import type { ConversationMessage } from "@/types/api"
import { INLINE_TURN_TOOL_NAME, splitConversationMessages } from "@/lib/ai-inline-turn-persistence"

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

export function conversationMessageToUI(message: ConversationMessage): UIMessage {
  return {
    id: message.id,
    role: message.role === "assistant" ? "assistant" : "user",
    parts: toolCallsToParts(message),
  }
}

export function conversationMessagesToUI(messages: ConversationMessage[]): UIMessage[] {
  const { chatMessages } = splitConversationMessages(messages)
  return chatMessages.map(conversationMessageToUI)
}
