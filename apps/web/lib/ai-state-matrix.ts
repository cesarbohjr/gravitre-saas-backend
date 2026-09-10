/**
 * AI State ↔ Backend State Matrix — live chat/voice activity labels.
 *
 * Unmapped or telemetry-shaped strings fail closed to SAFE_STATUS_FALLBACK.
 * Never render class names, logger levels, or snake_case codes.
 */

export const SAFE_STATUS_FALLBACK = "Working on it…"

const KNOWN_ACTIVITY_LABELS: Record<string, string> = {
  "cognitiveturnkernel pre-act complete": "Reviewing context and memory",
  "routing classified": "Understanding your request",
  "plan ready — running tools": "Running connected tools",
  "plan ready - running tools": "Running connected tools",
  "unified turn live": "Working on your request",
  orphan_plan_unclear_ask: "Waiting for your direction",
  "retrieve-before-generate": "Looking up a matching plan",
  "retrieve-before-generate (clarify, no fabrication)": "Looking up a matching plan",
  "conversational path (non-task)": "Replying",
  "swarm step-level transparency": "Summarizing agent work",
  "inline vendor preview": "Loading a preview",
  "conversational operator execution": "Running the requested action",
  "multi-step connector orchestration": "Coordinating connected tools",
  "governed connector execution": "Preparing a governed action",
  "react write gated for user approval": "Preparing something for your approval",
  "connector fallback after react": "Trying a connected-tool fallback",
  "analyzing your request": "Understanding your request",
  "reviewing connected systems and knowledge": "Checking your connected tools",
  "reviewing context and memory": "Reviewing context and memory",
}

const PREFIX_LABELS: Array<[string, string]> = [
  ["cognitiveturnkernel", "Reviewing context and memory"],
  ["unified turn live", "Working on your request"],
  ["retrieve-before-generate", "Looking up a matching plan"],
  ["clarification needed", "Figuring out what to ask next"],
  ["routing escalated", "Looking more closely at this request"],
]

const TOOL_STATUS_LABELS: Record<string, string> = {
  web_search: "Searching the web",
  search_web: "Searching the web",
  searchWeb: "Searching the web",
  knowledge_base: "Searching your knowledge base",
  searchKnowledgeBase: "Searching your knowledge base",
  agent_status: "Checking agent status",
  getAgentStatus: "Checking agent status",
  connector_status: "Checking connected tools",
  getConnectorStatus: "Checking connected tools",
  workflow_runs: "Listing workflow runs",
  getWorkflowRuns: "Listing workflow runs",
  schedules_list: "Listing schedules",
  listSchedules: "Listing schedules",
  analytics: "Checking analytics",
  getAnalytics: "Checking analytics",
  generate_document: "Generating a document",
  generateDocument: "Generating a document",
  run_agent_task: "Running the agent task",
  runAgentTask: "Running the agent task",
  create_workflow: "Creating a workflow",
  createWorkflow: "Creating a workflow",
  execute_workflow: "Executing the workflow",
  executeWorkflow: "Executing the workflow",
}

const KERNEL_TOKEN = /CognitiveTurnKernel|\bpre-ACT\b|\bkernel\b|cognitive_turn_kernel/i
const LOGGER_LEVEL = /\.(info|debug|warning|error|warn|critical)\b/i
const PASCAL_SERVICE = /\b(?:[A-Z][a-zA-Z0-9]+){0,3}(?:Kernel|Engine|Orchestrator|Service|Adapter)\b/
const SNAKE_CODE = /^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$/
const CAMEL_ID = /^[a-z]+(?:[A-Z][a-zA-Z0-9]+)+$/
const DOTTED_CATALOG = /^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+){2,}$/i
const SSE_PREFIX = /^(Running:|Completed:|Step \d+\/\d+:)\s*/i

function norm(text: string): string {
  return text.trim().toLowerCase().replace(/…/g, "").replace(/\s+/g, " ").trim()
}

export function looksLikeInternalStatus(text: string | null | undefined): boolean {
  const raw = (text || "").trim()
  if (!raw) return true
  if (KERNEL_TOKEN.test(raw)) return true
  if (LOGGER_LEVEL.test(raw)) return true
  if (PASCAL_SERVICE.test(raw)) return true
  const compact = raw.replace(/…/g, "").trim()
  if (SNAKE_CODE.test(compact)) return true
  if (CAMEL_ID.test(compact)) return true
  if (DOTTED_CATALOG.test(compact)) return true
  return false
}

export function specificConnectorStatus(connectors: string[] | null | undefined): string | null {
  const names = (connectors ?? [])
    .map((item) => strTitle(String(item || "").trim()))
    .filter(Boolean)
  if (names.length === 0) return null
  if (names.length === 1) return `Checking your ${names[0]} account`
  const shown = names.slice(0, 3)
  const extra = names.length - shown.length
  const joined = shown.join(", ")
  if (extra > 0) return `Checking ${names.length} connected tools (${joined}, +${extra} more)`
  return `Checking ${names.length} connected tools (${joined})`
}

function strTitle(value: string): string {
  if (!value) return ""
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (ch) => ch.toUpperCase())
}

function applyKnownOrPrefix(raw: string, connectors?: string[] | null): string | null {
  const mapped = KNOWN_ACTIVITY_LABELS[norm(raw)]
  if (mapped) {
    if (mapped.toLowerCase().includes("connected")) {
      const specific = specificConnectorStatus(connectors)
      if (specific) return specific
    }
    return mapped
  }
  const lower = raw.toLowerCase()
  for (const [prefix, label] of PREFIX_LABELS) {
    if (lower.startsWith(prefix)) {
      if (label.toLowerCase().includes("connected")) {
        const specific = specificConnectorStatus(connectors)
        if (specific) return specific
      }
      return label
    }
  }
  return null
}

export function specificToolStatus(
  toolName?: string | null,
  connectors?: string[] | null,
): string | null {
  const key = String(toolName || "").trim()
  if (!key) return null
  const mapped = TOOL_STATUS_LABELS[key] || TOOL_STATUS_LABELS[key.replace(/-/g, "_")]
  if (mapped) {
    if (mapped.toLowerCase().includes("connected")) {
      const specific = specificConnectorStatus(connectors)
      if (specific) return specific
    }
    return mapped
  }
  if (DOTTED_CATALOG.test(key)) {
    const parts = key.split(".")
    const vendor = strTitle(parts[0] || "")
    const resource = (parts[1] || "").replace(/_/g, " ")
    const verb = parts[parts.length - 1] || ""
    if (vendor && resource) {
      if (/search|list|get|find|read/i.test(verb)) return `Searching your ${vendor} ${resource}`
      if (/create|add|insert/i.test(verb)) return `Creating a ${vendor} ${resource.replace(/s$/, "")}`
      if (/update|patch|upsert/i.test(verb)) return `Updating ${vendor} ${resource}`
      return `Working in your ${vendor} ${resource}`
    }
  }
  if (looksLikeInternalStatus(key)) return null
  return key
}

export function sanitizeUserActivityLabel(
  text: string | null | undefined,
  options?: { connectors?: string[] | null; fallback?: string },
): string {
  const fallback = options?.fallback ?? SAFE_STATUS_FALLBACK
  const raw = (text || "").trim()
  if (!raw) return fallback
  const stripped = raw.replace(SSE_PREFIX, "").trim()
  if (stripped && stripped !== raw) {
    return sanitizeUserActivityLabel(stripped, options)
  }
  const known = applyKnownOrPrefix(raw, options?.connectors)
  if (known) return known
  if (looksLikeInternalStatus(raw)) return fallback
  return raw
}

export type UserStatusPayload = {
  label?: string | null
  internal?: boolean
}
