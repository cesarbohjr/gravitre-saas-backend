export type IntelligenceExecutionMode = "tools_executed" | "advisory_only" | "degraded"

export interface ExecutionModeFields {
  execution_mode?: IntelligenceExecutionMode
  executionMode?: IntelligenceExecutionMode
  tools_available?: number
  toolsAvailable?: number
  tool_call_count?: number
  toolCallCount?: number
  execution_verified?: boolean
  executionVerified?: boolean
}

const MODE_LABELS: Record<IntelligenceExecutionMode, string> = {
  tools_executed: "Tools executed",
  advisory_only: "Advisory only",
  degraded: "Degraded",
}

export function parseExecutionMode(value: unknown): IntelligenceExecutionMode | undefined {
  if (value === "tools_executed" || value === "advisory_only" || value === "degraded") {
    return value
  }
  return undefined
}

export function readExecutionModeFields(source: ExecutionModeFields | null | undefined) {
  const mode = parseExecutionMode(source?.executionMode ?? source?.execution_mode)
  const toolsAvailable = source?.toolsAvailable ?? source?.tools_available
  const toolCallCount = source?.toolCallCount ?? source?.tool_call_count
  const executionVerified = source?.executionVerified ?? source?.execution_verified
  return {
    mode,
    label: mode ? MODE_LABELS[mode] : undefined,
    toolsAvailable: typeof toolsAvailable === "number" ? toolsAvailable : undefined,
    toolCallCount: typeof toolCallCount === "number" ? toolCallCount : undefined,
    executionVerified: typeof executionVerified === "boolean" ? executionVerified : undefined,
  }
}
