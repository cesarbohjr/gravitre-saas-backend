"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { motion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { Search, Loader2, Clock, Sparkles, Trash2, X, ExternalLink } from "lucide-react"
import { cn } from "@/lib/utils"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { searchApi } from "@/lib/api"
import type { SearchResult, SearchHistoryItem } from "@/types/api"
import { toast } from "sonner"

const sampleQueries = [
  "failed runs in production today",
  "connectors with sync errors",
  "workflows using HubSpot",
  "agents active in finance",
]

export default function ChatPage() {
  const { user } = useAuth()
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<SearchResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [suggestions, setSuggestions] = useState<string[]>([])

  const { data: historyData, mutate: mutateHistory } = useSWR<{ searches: SearchHistoryItem[] }>(
    user ? "/api/search/history" : null,
    apiFetcher
  )

  const history = useMemo(() => historyData?.searches ?? [], [historyData])

  const handleSearch = async (nextQuery?: string) => {
    const effectiveQuery = (nextQuery ?? query).trim()
    if (!effectiveQuery) return
    setIsSearching(true)
    try {
      const response = await searchApi.search(effectiveQuery)
      setResults(response.results)
      setSuggestions(response.suggestions)
      setQuery(effectiveQuery)
      await mutateHistory()
    } catch (err) {
      console.error("[v0] Search failed:", err)
      toast.error("Search failed")
    } finally {
      setIsSearching(false)
    }
  }

  const handleClearHistory = async () => {
    try {
      await searchApi.clearHistory()
      await mutateHistory()
      toast.success("History cleared")
    } catch (err) {
      console.error("[v0] Clear history failed:", err)
      toast.error("Failed to clear history")
    }
  }

  const handleDeleteHistoryItem = async (id: string) => {
    try {
      await searchApi.deleteHistory(id)
      await mutateHistory()
    } catch (err) {
      console.error("[v0] Delete history item failed:", err)
      toast.error("Failed to remove item")
    }
  }

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    await handleSearch()
  }

  return (
    <AppShell title="Search">
      <div className="flex h-full flex-col md:flex-row">
        <div className="flex-1 flex flex-col min-w-0">
          <div className="border-b border-border px-4 md:px-6 py-3 md:py-4 bg-gradient-to-r from-card to-secondary/20">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 md:h-10 md:w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500/20 to-teal-500/20 ring-1 ring-emerald-500/20 shrink-0">
                  <Search className="h-4 w-4 md:h-5 md:w-5 text-emerald-400" />
                </div>
                <div className="min-w-0">
                  <h1 className="text-base md:text-lg font-semibold text-foreground">Semantic Search</h1>
                  <p className="text-xs md:text-sm text-muted-foreground truncate">
                    AI-powered search across workflows, agents, connectors, and docs
                  </p>
                </div>
              </div>
              <div className="text-xs text-muted-foreground">{results.length} result(s)</div>
            </div>
          </div>

          <div className="flex-1 p-4 md:p-6 overflow-auto">
            <div className="max-w-3xl mx-auto space-y-4">
              {results.length === 0 && !isSearching ? (
                <motion.div 
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex flex-col items-center justify-center py-16 text-center"
                >
                  <div className="relative mb-6">
                    <div className="h-20 w-20 rounded-full bg-gradient-to-br from-emerald-500/20 to-teal-500/20 flex items-center justify-center">
                      <Sparkles className="h-8 w-8 text-emerald-400" />
                    </div>
                    <motion.div
                      className="absolute inset-0 rounded-full border-2 border-emerald-500/30"
                      animate={{ scale: [1, 1.2, 1], opacity: [0.5, 0, 0.5] }}
                      transition={{ duration: 3, repeat: Infinity }}
                    />
                  </div>
                  <h2 className="text-lg font-semibold text-foreground mb-2">
                    What do you want to find?
                  </h2>
                  <p className="text-sm text-muted-foreground mb-8 max-w-md">
                    Use natural language to search your workflows, runs, connectors, agents, and documents.
                  </p>
                  <div className="flex flex-wrap justify-center gap-2">
                    {sampleQueries.map((q, i) => (
                      <button
                        key={i}
                        onClick={() => void handleSearch(q)}
                        className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-card/50 text-sm text-muted-foreground hover:text-foreground hover:border-foreground/20 transition-colors"
                      >
                        <Sparkles className="h-3 w-3" />
                        {q}
                      </button>
                    ))}
                  </div>
                </motion.div>
              ) : (
                <>
                  {isSearching && (
                    <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-card border border-border">
                      <Loader2 className="h-4 w-4 text-emerald-400 animate-spin" />
                      <span className="text-sm text-muted-foreground">Searching...</span>
                    </div>
                  )}
                  {results.map((result) => (
                    <motion.div
                      key={result.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="rounded-xl border border-border bg-card p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
                            {result.entity_type}
                          </p>
                          <h3 className="text-sm font-semibold text-foreground">{result.title}</h3>
                          {result.description && (
                            <p className="text-sm text-muted-foreground mt-1">{result.description}</p>
                          )}
                          {result.highlight && (
                            <p className="mt-2 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded px-2 py-1">
                              {result.highlight}
                            </p>
                          )}
                        </div>
                        <div className="text-right">
                          <p className="text-[10px] text-muted-foreground">score</p>
                          <p className="text-sm font-medium text-foreground">{result.score.toFixed(2)}</p>
                        </div>
                      </div>
                      <div className="mt-3">
                        <Link href={result.url} className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300">
                          Open result
                          <ExternalLink className="h-3 w-3" />
                        </Link>
                      </div>
                    </motion.div>
                  ))}
                </>
              )}
            </div>
          </div>

          <div className="border-t border-border p-4 bg-card/50">
            <form onSubmit={onSubmit} className="max-w-3xl mx-auto">
              <div className={cn(
                "flex items-center gap-3 rounded-lg border bg-card p-3 transition-all",
                "border-border hover:border-foreground/20 focus-within:border-blue-500/50 focus-within:ring-2 focus-within:ring-blue-500/20"
              )}>
                <input
                  type="text"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search workflows, runs, connectors, agents, or docs..."
                  disabled={isSearching}
                  className="flex-1 bg-transparent text-foreground placeholder:text-muted-foreground/50 focus:outline-none text-sm"
                />
                <Button
                  type="submit"
                  size="sm"
                  disabled={!query.trim() || isSearching}
                  className="gap-2"
                >
                  {isSearching ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Search className="h-4 w-4" />
                  )}
                </Button>
              </div>
              {suggestions.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {suggestions.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => void handleSearch(suggestion)}
                      className="text-xs px-2 py-1 rounded border border-border bg-secondary/40 hover:bg-secondary text-muted-foreground hover:text-foreground"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              )}
            </form>
          </div>
        </div>

        <div className="hidden lg:flex w-72 border-l border-border bg-card/30 flex-col">
          <div className="p-4 border-b border-border flex items-center justify-between">
            <div className="flex items-center gap-2 min-w-0">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <h2 className="text-sm font-semibold text-foreground truncate">Recent Searches</h2>
            </div>
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => void handleClearHistory()}>
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
          
          <div className="flex-1 overflow-auto p-2">
            {history.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center px-4">
                <Clock className="h-8 w-8 text-muted-foreground/30 mb-3" />
                <p className="text-xs text-muted-foreground">
                  Your search history will appear here
                </p>
              </div>
            ) : (
              <div className="space-y-1">
                {history.map((entry) => (
                  <button
                    key={entry.id}
                    onClick={() => void handleSearch(entry.query)}
                    className="w-full p-3 rounded-lg text-left hover:bg-secondary/50 transition-colors group"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm text-foreground truncate group-hover:text-blue-400 transition-colors">
                          {entry.query}
                        </p>
                        <span className="text-[10px] text-muted-foreground">
                          {new Date(entry.created_at).toLocaleString()} · {entry.results_count} results
                        </span>
                      </div>
                      <span
                        role="button"
                        tabIndex={0}
                        onClick={(event) => {
                          event.preventDefault()
                          event.stopPropagation()
                          void handleDeleteHistoryItem(entry.id)
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault()
                            event.stopPropagation()
                            void handleDeleteHistoryItem(entry.id)
                          }
                        }}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        <X className="h-3.5 w-3.5" />
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  )
}
