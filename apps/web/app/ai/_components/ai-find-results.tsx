"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import {
  Bot,
  Database,
  ExternalLink,
  FileText,
  Link2,
  Loader2,
  Sparkles,
  Workflow,
  Zap,
} from "lucide-react"
import { cn } from "@/lib/utils"
import type { SearchResult } from "@/types/api"

function statusBadgeClass(status: string): string {
  const normalized = status.toLowerCase()
  if (normalized.includes("fail") || normalized.includes("error")) {
    return "bg-red-500/10 text-red-500"
  }
  if (normalized.includes("run") || normalized.includes("progress")) {
    return "bg-blue-500/10 text-blue-500"
  }
  if (normalized.includes("success") || normalized.includes("complete")) {
    return "bg-emerald-500/10 text-emerald-500"
  }
  return "bg-muted text-muted-foreground"
}

function resolveResultStatus(result: SearchResult): string | null {
  const fromMeta = result.metadata?.status
  if (typeof fromMeta === "string" && fromMeta.trim()) return fromMeta.trim()
  const match = result.description?.match(/Status:\s*(.+)/i)
  return match?.[1]?.trim() ?? null
}

function formatRelativeTime(value: unknown): string | null {
  if (typeof value !== "string" || !value.trim()) return null
  const timestamp = new Date(value).getTime()
  if (Number.isNaN(timestamp)) return null
  const diffSeconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000))
  if (diffSeconds < 60) return "Just now"
  const diffMinutes = Math.floor(diffSeconds / 60)
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  return `${Math.floor(diffHours / 24)}d ago`
}

function SearchResultCard({ result }: { result: SearchResult }) {
  const status = resolveResultStatus(result)
  const relativeTime = formatRelativeTime(result.metadata?.created_at)
  const secondaryLine = result.description?.replace(/^Status:\s*/i, "").trim()

  return (
    <Link
      href={result.url}
      className="group flex items-start gap-3 rounded-xl border border-border bg-card/60 p-3 transition-colors hover:border-foreground/20 hover:bg-card"
    >
      <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-secondary/80">
        {result.entity_type === "run" ? (
          <Zap className="h-4 w-4 text-blue-400" />
        ) : result.entity_type === "agent" ? (
          <Bot className="h-4 w-4 text-violet-400" />
        ) : result.entity_type === "connector" ? (
          <Link2 className="h-4 w-4 text-emerald-400" />
        ) : result.entity_type === "workflow" ? (
          <Workflow className="h-4 w-4 text-amber-400" />
        ) : result.entity_type === "source" ? (
          <Database className="h-4 w-4 text-cyan-400" />
        ) : (
          <FileText className="h-4 w-4 text-muted-foreground" />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground group-hover:text-blue-500">
              {result.title}
            </p>
            {secondaryLine ? (
              <p className="mt-0.5 truncate text-xs text-muted-foreground">{secondaryLine}</p>
            ) : null}
            {result.highlight && result.highlight !== secondaryLine ? (
              <p className="mt-1 line-clamp-1 text-xs text-emerald-500/90">{result.highlight}</p>
            ) : null}
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            {status ? (
              <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium capitalize", statusBadgeClass(status))}>
                {status.replace(/_/g, " ")}
              </span>
            ) : null}
            {relativeTime ? (
              <span className="text-[10px] text-muted-foreground">{relativeTime}</span>
            ) : null}
          </div>
        </div>
      </div>
      <ExternalLink className="mt-1 h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
    </Link>
  )
}

type AiFindResultsProps = {
  results: SearchResult[]
  suggestions: string[]
  isSearching: boolean
  onSuggestionSelect?: (query: string) => void
}

export function AiFindResults({
  results,
  suggestions,
  isSearching,
  onSuggestionSelect,
}: AiFindResultsProps) {
  if (isSearching) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-border bg-card/60 p-4 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin text-amber-500" />
        Searching your workspace…
      </div>
    )
  }

  if (results.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card/50 p-4">
        <p className="text-sm text-muted-foreground">No matches found. Try a shorter query.</p>
        {suggestions.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {suggestions.map((chip) => (
              <button
                key={chip}
                type="button"
                onClick={() => onSuggestionSelect?.(chip)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground"
              >
                <Sparkles className="h-3 w-3" />
                {chip}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {results.length} result{results.length === 1 ? "" : "s"}
      </p>
      <div className="space-y-2">
        {results.map((result, index) => (
          <motion.div
            key={result.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.04 }}
          >
            <SearchResultCard result={result} />
          </motion.div>
        ))}
      </div>
    </div>
  )
}
