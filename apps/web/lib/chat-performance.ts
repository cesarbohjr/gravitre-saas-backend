/** Client-side chat performance instrumentation. */

export type ChatPerfStage =
  | "page_load"
  | "conversation_load"
  | "first_token"
  | "total_response"
  | "connector_status"
  | "knowledge_search"
  | "tool_selection"
  | "tool_execution"

type PerfMark = {
  stage: ChatPerfStage
  ms: number
  at: number
}

const marks: PerfMark[] = []
const stageStarts = new Map<string, number>()

export function startChatPerf(stage: ChatPerfStage, key: string = stage): void {
  stageStarts.set(key, performance.now())
}

export function endChatPerf(stage: ChatPerfStage, key: string = stage): number | null {
  const started = stageStarts.get(key)
  if (started == null) return null
  const ms = Math.round(performance.now() - started)
  marks.push({ stage, ms, at: Date.now() })
  stageStarts.delete(key)
  if (typeof window !== "undefined" && process.env.NODE_ENV === "development") {
    console.debug(`[chat-perf] ${stage}: ${ms}ms`)
  }
  return ms
}

export function markChatPerf(stage: ChatPerfStage, ms: number): void {
  marks.push({ stage, ms, at: Date.now() })
  if (typeof window !== "undefined" && process.env.NODE_ENV === "development") {
    console.debug(`[chat-perf] ${stage}: ${ms}ms`)
  }
}

export function getChatPerfMarks(): PerfMark[] {
  return [...marks]
}

export function resetChatPerf(): void {
  marks.length = 0
  stageStarts.clear()
}
