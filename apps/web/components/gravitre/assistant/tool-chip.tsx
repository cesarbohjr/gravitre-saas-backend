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

  if (toolName === "getConnectorStatus" && Array.isArray(data.connectors)) {
    const connectors = data.connectors as { status?: string }[]
    if (connectors.length === 0) return "warning"
    if (connectors.every((c) => c.status === "pending_auth" || c.status === "disconnected")) {
      return "warning"
    }
  }

  return "success"
}

function getToolLabel(name: string, result: unknown, outcome: ToolOutcome) {
  if (outcome === "error") {
    switch (name) {
      case "searchWeb": return "Web search unavailable"
      case "searchKnowledgeBase": return "Knowledge search failed"
      default: return "Tool failed"
    }
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
    return "bg-zinc-800 text-zinc-400 border border-zinc-700"
  }
  if (outcome === "error") {
    return "bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 cursor-pointer"
  }
  if (outcome === "warning") {
    return "bg-amber-500/10 text-amber-400 border border-amber-500/20 hover:bg-amber-500/20 cursor-pointer"
  }
  return "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 cursor-pointer"
}

function renderToolDetails(toolName: string, result: unknown) {
  const data = asRecord(result)
  if (!data) return <p className="text-zinc-500">No results</p>

  const error = typeof data.error === "string" ? data.error.trim() : ""
  if (error) {
    return <p className="text-red-300">{error}</p>
  }

  if (toolName === "searchKnowledgeBase" && Array.isArray(data.results)) {
    if (data.results.length === 0) {
      return (
        <div className="space-y-2 text-amber-300">
          <p>No matching documents in your knowledge base.</p>
          <Link href="/connectors" className="text-emerald-400 hover:underline text-[11px]">
            Connect sources and enable knowledge sync →
          </Link>
        </div>
      )
    }
    return (
      <ul className="space-y-1.5">
        {(data.results as { title?: string; relevance?: number }[]).slice(0, 5).map((item, i) => (
          <li key={i} className="text-zinc-300">
            • {item.title || "Document"} — {Math.round((item.relevance || 0) * 100)}% match
          </li>
        ))}
      </ul>
    )
  }

  if (toolName === "getConnectorStatus" && Array.isArray(data.connectors)) {
    const connectors = data.connectors as { name?: string; type?: string; status?: string }[]
    if (connectors.length === 0) {
      return (
        <div className="space-y-2 text-amber-300">
          <p>No integrations connected yet.</p>
          <Link href="/connectors" className="text-emerald-400 hover:underline text-[11px]">
            Connect CRM, docs, and analytics →
          </Link>
        </div>
      )
    }
    return (
      <div className="space-y-2">
        <ul className="space-y-1">
          {connectors.map((c, i) => (
            <li key={i} className="text-zinc-300">
              • {c.name || c.type} — {c.status}
              {c.status === "pending_auth" ? " ⚠️" : ""}
            </li>
          ))}
        </ul>
        {connectors.some((c) => c.status === "pending_auth") && (
          <Link href="/connectors" className="text-emerald-400 hover:underline text-[11px]">
            Fix authentication →
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
            <li key={i} className="text-zinc-300">
              • {run.workflowName || run.name || "Run"} — {run.status === "failed" ? "✗ Failed" : "✓ Success"}
            </li>
          ))}
        </ul>
        <Link href="/workflows" className="text-emerald-400 hover:underline text-[11px]">
          View all runs →
        </Link>
      </div>
    )
  }

  if (toolName === "searchWeb") {
    if (error) {
      return <p className="text-red-300">{error}</p>
    }
    if (data.query) {
      const results = Array.isArray(data.results) ? data.results : []
      const sources = Array.isArray(data.sources) ? data.sources : []
      const count = typeof data.totalResults === "number" ? data.totalResults : results.length || sources.length
      if (count === 0) {
        return (
          <div className="space-y-1 text-amber-300">
            <p>Query: {String(data.query)}</p>
            <p>No web results returned.</p>
          </div>
        )
      }
      return (
        <div className="space-y-1 text-zinc-300">
          <p>Query: {String(data.query)}</p>
          <p>Sources: {count} results</p>
        </div>
      )
    }
  }

  if (toolName === "generateDocument" && data.title) {
    return (
      <div className="space-y-1 text-zinc-300">
        <p>Generated: {String(data.title)}</p>
        {data.wordCount != null && <p>Format: Markdown, {String(data.wordCount)} words</p>}
      </div>
    )
  }

  return (
    <pre className="text-zinc-300 overflow-x-auto whitespace-pre-wrap font-mono">
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

export function ToolChip({
  invocation,
  expanded,
  onToggle,
}: {
  invocation: ToolInvocation
  expanded: boolean
  onToggle: () => void
}) {
  const isComplete = invocation.state === "result"
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
            <div className="mt-2 p-3 rounded-lg bg-zinc-900 border border-zinc-800 text-xs">
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
    const output = tool.result as { connectors?: { name?: string; type?: string; status?: string }[] }
    const pending = (output.connectors || []).filter((c) => c.status === "pending_auth")
    if (pending.length) return pending
  }
  return []
}
