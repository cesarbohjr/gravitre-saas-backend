"use client"

import { useState } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import {
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

function getToolLabel(name: string) {
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

function renderToolDetails(toolName: string, result: unknown) {
  const data = result as Record<string, unknown> | null
  if (!data) return <p className="text-zinc-500">No results</p>

  if (toolName === "searchKnowledgeBase" && Array.isArray(data.results)) {
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

  if (toolName === "searchWeb" && data.query) {
    return (
      <div className="space-y-1 text-zinc-300">
        <p>Query: {String(data.query)}</p>
        {Array.isArray(data.sources) && <p>Sources: {(data.sources as unknown[]).length} results</p>}
      </div>
    )
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
  const Icon = toolIcons[invocation.toolName] || Database
  const duration = invocation.durationMs != null ? ` (${(invocation.durationMs / 1000).toFixed(1)}s)` : ""

  return (
    <div className="my-2">
      <button
        onClick={() => isComplete && onToggle()}
        disabled={!isComplete}
        className={cn(
          "inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
          isComplete
            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 cursor-pointer"
            : "bg-zinc-800 text-zinc-400 border border-zinc-700",
        )}
      >
        {isComplete ? <Check className="h-3 w-3" /> : <Loader2 className="h-3 w-3 animate-spin" />}
        <Icon className="h-3 w-3" />
        <span>{getToolLabel(invocation.toolName)}{isComplete ? duration : "..."}</span>
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
