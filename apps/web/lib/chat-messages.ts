import type { UIMessage } from "ai"
import type { ConversationMessage } from "@/types/api"

export function conversationMessageToUI(message: ConversationMessage): UIMessage {
  return {
    id: message.id,
    role: message.role === "assistant" ? "assistant" : "user",
    parts: [{ type: "text", text: message.content }],
  }
}
