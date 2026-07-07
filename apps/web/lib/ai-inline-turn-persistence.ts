import type { AiEngine } from "@/lib/ai-surface-handoff"
import type { InlineExecutePlan } from "@/lib/ai-inline-execute"
import type { SearchResult } from "@/types/api"
import type { ConversationMessage } from "@/types/api"

export const INLINE_TURN_TOOL_NAME = "gravitre.inline_turn"

export type PersistedInlineTurn = {
  id: string
  prompt: string
  engine: AiEngine
  status: "running" | "completed" | "failed"
  executePlan?: InlineExecutePlan | null
  executeError?: string | null
  findResults?: SearchResult[]
  findSuggestions?: string[]
  findError?: string | null
}

function summarizeInlineTurn(turn: PersistedInlineTurn): string {
  if (turn.engine === "find") {
    const count = turn.findResults?.length ?? 0
    if (turn.findError) return turn.findError
    return count > 0
      ? `Found ${count} result${count === 1 ? "" : "s"} for your search.`
      : "Search completed with no matching records."
  }
  if (turn.engine === "execute") {
    if (turn.executeError) return turn.executeError
    const finding = turn.executePlan?.findings?.[0]?.content
    if (finding) return finding
    return "Analysis completed — review the results below."
  }
  return "Task completed."
}

export function serializeInlineTurn(turn: PersistedInlineTurn): ConversationMessage[] {
  const assistantSummary = summarizeInlineTurn(turn)
  return [
    {
      id: `${turn.id}-user`,
      conversation_id: "",
      role: "user",
      content: turn.prompt,
      created_at: new Date().toISOString(),
    },
    {
      id: `${turn.id}-assistant`,
      conversation_id: "",
      role: "assistant",
      content: assistantSummary,
      tool_calls: [
        {
          name: INLINE_TURN_TOOL_NAME,
          input: turn,
        },
      ],
      created_at: new Date().toISOString(),
    },
  ]
}

function readInlineTurnFromToolCalls(toolCalls: unknown): PersistedInlineTurn | null {
  if (!Array.isArray(toolCalls)) return null
  for (const entry of toolCalls) {
    if (!entry || typeof entry !== "object") continue
    const row = entry as { name?: string; input?: unknown }
    if (row.name !== INLINE_TURN_TOOL_NAME || !row.input || typeof row.input !== "object") continue
    const input = row.input as PersistedInlineTurn
    if (!input.id || !input.prompt || !input.engine) continue
    return {
      id: input.id,
      prompt: input.prompt,
      engine: input.engine,
      status: input.status ?? "completed",
      executePlan: input.executePlan ?? null,
      executeError: input.executeError ?? null,
      findResults: input.findResults,
      findSuggestions: input.findSuggestions,
      findError: input.findError ?? null,
    }
  }
  return null
}

export function splitConversationMessages(messages: ConversationMessage[]): {
  chatMessages: ConversationMessage[]
  inlineTurns: PersistedInlineTurn[]
} {
  const chatMessages: ConversationMessage[] = []
  const inlineTurns: PersistedInlineTurn[] = []

  for (let index = 0; index < messages.length; index += 1) {
    const message = messages[index]
    const next = messages[index + 1]
    if (
      message.role === "user" &&
      next?.role === "assistant" &&
      readInlineTurnFromToolCalls(next.tool_calls)
    ) {
      continue
    }
    const inlineTurn = message.role === "assistant" ? readInlineTurnFromToolCalls(message.tool_calls) : null
    if (inlineTurn) {
      inlineTurns.push(inlineTurn)
      continue
    }
    chatMessages.push(message)
  }

  return { chatMessages, inlineTurns }
}
