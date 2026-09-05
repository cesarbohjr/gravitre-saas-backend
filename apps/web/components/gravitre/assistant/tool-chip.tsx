"use client"

import { useState } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import {
  AlertCircle,
  AlertTriangle,
  BarChart3,
  Bot,
  Check,
  ChevronDown,
  Database,
  FileText,
  Globe,
  Loader2,
  Plug,
  Search,
  Workflow,
  Play,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { STATUS } from "@/lib/design-system"
import {
  FileReferenceChipRow,
  hostedFilesFromUnknown,
} from "@/components/gravitre/assistant/file-reference-chip"
import {
  PreviewCodePane,
  previewPropsFromToolResult,
} from "@/components/gravitre/assistant/preview-code-pane"

const toolIcons: Record<string, typeof Database> = {
  searchKnowledgeBase: Search,
  getAgentStatus: Bot,
  getConnectorStatus: Plug,
  getWorkflowRuns: Workflow,
  getAnalytics: BarChart3,
  searchWeb: Globe,
  generateDocument: FileText,
  runAgentTask: Play,
  createWorkflow: Workflow,
}

export interface ToolInvocation {
  toolCallId: string
  toolName: string
  state: "call" | "result"
  result?: unknown
  durationMs?: number
}

type ToolOutcome = "success" | "warning" | "error"

type ConnectorStatusRow = {
  name?: string
  type?: string
  vendor?: string
  status?: string
  display_status?: string
  execution_available?: boolean
  blocking_reason?: string
  recovery_action?: string
  connected?: boolean
}

function connectorStatusRows(result: unknown): ConnectorStatusRow[] {
  const data = asRecord(result)
  if (!data || !Array.isArray(data.connectors)) return []
  return data.connectors as ConnectorStatusRow[]
}

function connectorStatusLine(row: ConnectorStatusRow): string {
  const label = row.name || row.type || row.vendor || "Connector"
  if (row.execution_available) return `${label} — connected and executable`
  const reason = String(row.blocking_reason || "").trim()
  if (reason === "token_expired") {
    return `${label} — authentication expired (reconnect required)`
  }
  if (reason === "missing_scope") {
    return `${label} — connected, missing OAuth scopes`
  }
  if (reason === "unsupported_action") {
    return `${label} — connected, action unsupported`
  }
  if (reason === "pending_auth") {
    return `${label} — authentication required`
  }
  const status = row.display_status || row.status || "unknown"
  return `${label} — ${status}`
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  return null
}

function getToolOutcome(toolName: string, result: unknown): ToolOutcome {
  const data = asRecord(result)
  if (!data) return "warning"

  const error = typeof data.error === "string" ? data.error.trim() : ""
  if (error) return "error"
  if (data.success === false) return "error"

  if (toolName === "searchKnowledgeBase") {
    const total = typeof data.totalResults === "number" ? data.totalResults : undefined
    const results = Array.isArray(data.results) ? data.results : []
    if ((total ?? results.length) === 0) return "warning"
  }

  if (toolName === "searchWeb") {
    const total = typeof data.totalResults === "number" ? data.totalResults : undefined
    const results = Array.isArray(data.results) ? data.results : []
    const sources = Array.isArray(data.sources) ? data.sources : []
    if ((total ?? results.length ?? sources.length) === 0) return "warning"
  }

  if (toolName === "getConnectorStatus") {
    const connectors = connectorStatusRows(result)
    if (connectors.length === 0) return "warning"
    if (connectors.every((c) => !c.execution_available)) return "warning"
    if (connectors.some((c) => c.blocking_reason === "token_expired")) return "warning"
    return "success"
  }

  return "success"
}

function errorCodeLabel(result: unknown): string | null {
  const data = asRecord(result)
  const code = data?.errorCode ?? data?.error_code
  return typeof code === "string" && code.trim() ? code.trim() : null
}

export function isInternalToolGateResult(result: unknown): boolean {
  const data = asRecord(result)
  if (!data) return false
  const code = String(data.errorCode ?? data.error_code ?? "").trim().toLowerCase()
  if (code === "write_approval_required") return true
  if (Boolean(data.pending_approval)) return true
  const err = String(data.error ?? "").trim().toLowerCase()
  return err.includes("write actions require explicit user approval")
}

function friendlyToolErrorLabel(toolName: string, result: unknown): string {
  const code = (errorCodeLabel(result) || "").toLowerCase()
  if (code === "write_approval_required") return "Awaiting your approval"
  if (code === "validation_error") return "Needs a few more details"
  if (code === "capability_ambiguous") return "Need you to pick a system"
  switch (toolName) {
    case "searchWeb":
      return "Web search unavailable"
    case "searchKnowledgeBase":
      return "Knowledge search unavailable"
    default:
      return "That step did not complete"
  }
}

function getToolLabel(name: string, result: unknown, outcome: ToolOutcome) {
  if (outcome === "error") {
    if (isInternalToolGateResult(result)) return "Preparing approval"
    return friendlyToolErrorLabel(name, result)
  }
  if (outcome === "warning") {
    switch (name) {
      case "searchWeb": return "Web search returned no results"
      case "searchKnowledgeBase": return "No knowledge matches"
      case "getConnectorStatus": return "No connectors connected"
      default: return "No results"
    }
  }
  switch (name) {
    case "searchKnowledgeBase": return "Searched knowledge base"
    case "getAgentStatus": return "Checked agent status"
    case "getConnectorStatus": return "Checked connector status"
    case "getWorkflowRuns": return "Listed workflow runs"
    case "getAnalytics": return "Loaded org analytics"
    case "searchWeb": return "Searched the web"
    case "generateDocument": return "Generated document"
    case "runAgentTask": return "Ran agent task"
    case "createWorkflow": return "Created draft workflow"
    default: return name
  }
}

function outcomeStyles(outcome: ToolOutcome, isComplete: boolean) {
  if (!isComplete) {
    return STATUS.running
  }
  if (outcome === "error") {
    return cn(STATUS.failed, "hover:opacity-90 cursor-pointer")
  }
  if (outcome === "warning") {
    return cn(STATUS.pending, "hover:opacity-90 cursor-pointer")
  }
  return cn(STATUS.verified, "hover:opacity-90 cursor-pointer")
}

function renderToolDetails(toolName: string, result: unknown) {
  const data = asRecord(result)
  if (!data) return <p className="text-muted-foreground">No results</p>

  const error = typeof data.error === "string" ? data.error.trim() : ""
  const errorCode = typeof data.errorCode === "string" ? data.errorCode.trim() : ""
  if (error || errorCode) {
    if (isInternalToolGateResult(data)) {
      return <p className="text-muted-foreground">Waiting for your approval before running this.</p>
    }
    return (
      <div className="space-y-1 text-destructive">
        {error ? <p>{error}</p> : null}
      </div>
    )
  }

  if (toolName === "searchKnowledgeBase" && Array.isArray(data.results)) {
    if (data.results.length === 0) {
      return (
        <div className="space-y-2 text-[color:var(--status-pending)]">
          <p>No matching documents in your knowledge base.</p>
          <Link href="/connectors" className="text-primary hover:underline text-[11px]">
            Connect sources and enable knowledge sync →
          </Link>
        </div>
      )
    }
    return (
      <ul className="space-y-1.5">
        {(data.results as { title?: string; relevance?: number }[]).slice(0, 5).map((item, i) => (
          <li key={i} className="text-foreground/90">
            • {item.title || "Document"} — {Math.round((item.relevance || 0) * 100)}% match
          </li>
        ))}
      </ul>
    )
  }

  if (toolName === "getConnectorStatus") {
    const connectors = connectorStatusRows(result)
    if (connectors.length === 0) {
      return (
        <div className="space-y-2 text-[color:var(--status-pending)]">
          <p>No integrations connected yet.</p>
          <Link href="/connectors" className="text-primary hover:underline text-[11px]">
            Connect CRM, docs, and analytics →
          </Link>
        </div>
      )
    }
    const needsAuth = connectors.some(
      (c) =>
        c.blocking_reason === "pending_auth" ||
        c.blocking_reason === "token_expired" ||
        c.status === "pending_auth" ||
        c.display_status === "disconnected",
    )
    return (
      <div className="space-y-2">
        <ul className="space-y-1">
          {connectors.map((c, i) => (
            <li key={i} className="text-foreground/90">
              • {connectorStatusLine(c)}
            </li>
          ))}
        </ul>
        {needsAuth && (
          <Link href="/connectors" className="text-primary hover:underline text-[11px]">
            Fix authentication on Connectors →
          </Link>
        )}
      </div>
    )
  }

  if (toolName === "getWorkflowRuns" && Array.isArray(data.runs)) {
    return (
      <div className="space-y-2">
        <ul className="space-y-1">
          {(data.runs as { workflowName?: string; name?: string; status?: string }[]).slice(0, 5).map((run, i) => (
            <li key={i} className="text-foreground/90">
              • {run.workflowName || run.name || "Run"} — {run.status === "failed" ? "✗ Failed" : "✓ Success"}
            </li>
          ))}
        </ul>
        <Link href="/workflows" className="text-primary hover:underline text-[11px]">
          View all runs →
        </Link>
      </div>
    )
  }

  if (toolName === "searchWeb") {
    if (error) {
      return <p className="text-destructive">{error}</p>
    }
    if (data.query) {
      const results = Array.isArray(data.results) ? data.results : []
      const sources = Array.isArray(data.sources) ? data.sources : []
      const count = typeof data.totalResults === "number" ? data.totalResults : results.length || sources.length
      if (count === 0) {
        return (
          <div className="space-y-1 text-[color:var(--status-pending)]">
            <p>Query: {String(data.query)}</p>
            <p>No web results returned.</p>
          </div>
        )
      }
      return (
        <div className="space-y-1 text-foreground/90">
          <p>Query: {String(data.query)}</p>
          <p>Sources: {count} results</p>
        </div>
      )
    }
  }

  if (toolName === "generateDocument" && data.title) {
    return (
      <div className="space-y-1 text-foreground/90">
        <p>Generated: {String(data.title)}</p>
        {data.wordCount != null && <p>Format: Markdown, {String(data.wordCount)} words</p>}
        <FileReferenceChipRow files={hostedFilesFromUnknown(data)} className="mt-2" />
        <PreviewCodePane
          {...(previewPropsFromToolResult(data) || {})}
          title={String(data.title)}
          className="mt-2 border-border bg-muted/50"
        />
      </div>
    )
  }

  if (toolName === "getAnalytics" || toolName === "codeTransform") {
    const preview = previewPropsFromToolResult(data)
    const files = hostedFilesFromUnknown(data)
    if (preview || files.length) {
      return (
        <div className="space-y-1 text-foreground/90">
          {toolName === "getAnalytics" ? (
            <p>
              Runs (7d):{" "}
              {String(
                (data.last7Days as { totalRuns?: number } | undefined)?.totalRuns ??
                  "—",
              )}
            </p>
          ) : (
            <p>{String(data.description || data.preview || "Transform complete")}</p>
          )}
          <FileReferenceChipRow files={files} className="mt-2" />
          {preview ? (
            <PreviewCodePane
              {...preview}
              className="mt-2 border-border bg-muted/50"
            />
          ) : null}
        </div>
      )
    }
  }

  return (
    <pre className="text-foreground/90 overflow-x-auto whitespace-pre-wrap font-mono">
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

export function ToolChip({
  invocation,
  expanded: expandedProp,
  onToggle: onToggleProp,
}: {
  invocation: ToolInvocation
  expanded?: boolean
  onToggle?: () => void
}) {
  const [internalExpanded, setInternalExpanded] = useState(false)
  const expanded = expandedProp ?? internalExpanded
  const onToggle = onToggleProp ?? (() => setInternalExpanded((value) => !value))
  const isComplete = invocation.state === "result"
  if (isComplete && isInternalToolGateResult(invocation.result)) {
    return null
  }
  const outcome = isComplete ? getToolOutcome(invocation.toolName, invocation.result) : "success"
  const Icon = toolIcons[invocation.toolName] || Database
  const duration = invocation.durationMs != null ? ` (${(invocation.durationMs / 1000).toFixed(1)}s)` : ""
  const StatusIcon =
    !isComplete ? Loader2 : outcome === "error" ? AlertCircle : outcome === "warning" ? AlertTriangle : Check

  return (
    <div className="my-2">
      <button
        onClick={() => isComplete && onToggle()}
        disabled={!isComplete}
        className={cn(
          "inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
          outcomeStyles(outcome, isComplete),
        )}
      >
        <StatusIcon className={cn("h-3 w-3", !isComplete && "animate-spin")} />
        <Icon className="h-3 w-3" />
        <span>{getToolLabel(invocation.toolName, invocation.result, outcome)}{isComplete ? duration : "..."}</span>
        {isComplete && <ChevronDown className={cn("h-3 w-3 transition-transform", expanded && "rotate-180")} />}
      </button>

      <AnimatePresence>
        {expanded && invocation.result != null && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
            <div className="mt-2 rounded-lg border border-border bg-muted/40 p-3 text-xs text-foreground">
              {renderToolDetails(invocation.toolName, invocation.result)}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export function extractPendingAuthConnectors(tools: ToolInvocation[]) {
  for (const tool of tools) {
    if (tool.toolName !== "getConnectorStatus" || !tool.result) continue
    const pending = connectorStatusRows(tool.result).filter(
      (c) =>
        c.blocking_reason === "pending_auth" ||
        c.blocking_reason === "token_expired" ||
        c.status === "pending_auth",
    )
    if (pending.length) return pending
  }
  return []
}
