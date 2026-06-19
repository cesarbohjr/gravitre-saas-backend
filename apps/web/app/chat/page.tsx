"use client"

import { useMemo, useState, useRef, useEffect, useCallback } from "react"
import useSWR from "swr"
import { motion, AnimatePresence, type Variants } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { useWorkPageShortcut } from "@/hooks/use-work-page-shortcut"
import { Search, Loader2, Clock, Sparkles, Trash2, X, ExternalLink, Command, Zap, Bot, Link2, Workflow, Database, FileText, type LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { useMotionPrefs, hoverLift, pressScale } from "@/lib/animations"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { AnimatedCounter } from "@/components/gravitre/premium-effects"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { searchApi, assistantApi } from "@/lib/api"
import { ensureSelectedOrg } from "@/lib/org-context"
import {
  buildOrgSearchChips,
  buildFallbackSearchChips,
  buildSearchPlaceholders,
  buildFallbackSearchPlaceholders,
  type SearchSuggestionChip,
} from "@/lib/search-suggestion-chips"
import {
  buildSearchTypeaheadItems,
  type SearchTypeaheadItem,
} from "@/lib/search-typeahead"
import { consumeFocusSearchAfterNav } from "@/lib/work-page-shortcuts"
import type { SearchResult, SearchHistoryItem } from "@/types/api"
import { toast } from "sonner"

const CHIP_STAGGER_S = 0.08

const chipListVariants: Variants = {
  initial: {},
  animate: {
    transition: { staggerChildren: CHIP_STAGGER_S, delayChildren: 0.04 },
  },
}

function chipItemVariants(reduced: boolean): Variants {
  return reduced
    ? {
        initial: { opacity: 0 },
        animate: { opacity: 1, transition: { duration: 0.15 } },
      }
    : {
        initial: { opacity: 0, y: 20 },
        animate: {
          opacity: 1,
          y: 0,
          transition: { duration: 0.35, ease: "easeOut" },
        },
      }
}

type SearchEntityType = SearchResult["entity_type"]

const SEARCH_GROUP_CONFIG: Array<{
  key: SearchEntityType
  label: string
  icon: LucideIcon
}> = [
  { key: "run", label: "Workflow Runs", icon: Zap },
  { key: "workflow", label: "Workflows", icon: Workflow },
  { key: "agent", label: "Agents", icon: Bot },
  { key: "connector", label: "Connectors", icon: Link2 },
  { key: "source", label: "Sources", icon: Database },
  { key: "document", label: "Documents", icon: FileText },
]

// Worked examples that teach how to phrase a search and what comes back.
// These are phrasing templates, not claims about specific records.
const SEARCH_QUERY_PATTERNS: Array<{ query: string; returns: string; icon: LucideIcon }> = [
  {
    query: "failed runs in the last 24 hours",
    returns: "Recent workflow runs that errored, newest first.",
    icon: Zap,
  },
  {
    query: "workflows using the Slack connector",
    returns: "Workflows wired to a specific connector or source.",
    icon: Workflow,
  },
]

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
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `${diffDays}d ago`
  return new Date(value).toLocaleDateString()
}

function statusBadgeClass(status: string): string {
  const normalized = status.toLowerCase()
  if (normalized.includes("fail") || normalized.includes("error") || normalized.includes("disconnect")) {
    return "bg-red-500/10 text-red-400"
  }
  if (
    normalized.includes("auth") ||
    normalized.includes("degrad") ||
    normalized.includes("warn") ||
    normalized.includes("pending")
  ) {
    return "bg-amber-500/10 text-amber-400"
  }
  if (
    normalized.includes("active") ||
    normalized.includes("complete") ||
    normalized.includes("success") ||
    normalized.includes("connected") ||
    normalized.includes("idle")
  ) {
    return "bg-emerald-500/10 text-emerald-400"
  }
  if (normalized.includes("run")) {
    return "bg-blue-500/10 text-blue-400"
  }
  return "bg-secondary text-muted-foreground"
}

function formatStatusLabel(status: string): string {
  const normalized = status.toLowerCase()
  if (normalized.includes("auth") && normalized.includes("need")) return "Auth needed"
  if (normalized.includes("error") || normalized.includes("fail")) return "Failed"
  if (normalized.includes("active")) return "Active"
  if (normalized.includes("running")) return "Running"
  return status.replace(/_/g, " ")
}

function groupSearchResults(results: SearchResult[]) {
  const byType = new Map<SearchEntityType, SearchResult[]>()
  for (const result of results) {
    const bucket = byType.get(result.entity_type) ?? []
    bucket.push(result)
    byType.set(result.entity_type, bucket)
  }
  return SEARCH_GROUP_CONFIG.map((group) => ({
    ...group,
    items: byType.get(group.key) ?? [],
  })).filter((group) => group.items.length > 0)
}

function SearchResultRow({
  result,
  reduced,
  motionVariant,
}: {
  result: SearchResult
  reduced: boolean
  motionVariant?: Variants
}) {
  const status = resolveResultStatus(result)
  const relativeTime = formatRelativeTime(result.metadata?.created_at)
  const secondaryLine = result.description?.replace(/^Status:\s*/i, "").trim()

  return (
    <motion.div
      layout={!reduced}
      variants={motionVariant}
      whileHover={reduced ? undefined : { x: 2 }}
    >
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
              <p className="truncate text-sm font-semibold text-foreground group-hover:text-blue-400 transition-colors">
                {result.title}
              </p>
              {secondaryLine ? (
                <p className="truncate text-xs text-muted-foreground mt-0.5">{secondaryLine}</p>
              ) : null}
              {result.highlight && result.highlight !== secondaryLine ? (
                <p className="mt-1 line-clamp-1 text-xs text-emerald-400/90">{result.highlight}</p>
              ) : null}
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1">
              {status ? (
                <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium capitalize", statusBadgeClass(status))}>
                  {formatStatusLabel(status)}
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
    </motion.div>
  )
}

function SearchSuggestionChips({
  chips,
  reduced,
  disabled,
  onSelect,
  className,
}: {
  chips: SearchSuggestionChip[]
  reduced: boolean
  disabled?: boolean
  onSelect: (label: string) => void
  className?: string
}) {
  return (
    <motion.div
      variants={chipListVariants}
      initial="initial"
      animate="animate"
      className={cn("flex flex-wrap justify-center gap-2", className)}
    >
      {chips.map((chip) => (
        <motion.button
          key={chip.id}
          variants={chipItemVariants(reduced)}
          whileHover={reduced || disabled ? undefined : hoverLift}
          whileTap={reduced || disabled ? undefined : pressScale}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(chip.label)}
          className={cn(
            "flex items-center gap-2 rounded-lg border border-border bg-card/50 px-3 py-2 text-sm text-muted-foreground transition-colors",
            "hover:border-foreground/20 hover:text-foreground",
            disabled && "pointer-events-none opacity-60",
          )}
        >
          <Sparkles className="h-3 w-3 shrink-0" />
          {chip.label}
        </motion.button>
      ))}
    </motion.div>
  )
}

const TYPEAHEAD_KIND_ICON: Record<SearchTypeaheadItem["kind"], LucideIcon> = {
  agent: Bot,
  workflow: Workflow,
  connector: Link2,
  history: Clock,
  search: Search,
}

function SearchTypeaheadDropdown({
  items,
  activeIndex,
  onHover,
  onSelect,
}: {
  items: SearchTypeaheadItem[]
  activeIndex: number
  onHover: (index: number) => void
  onSelect: (item: SearchTypeaheadItem) => void
}) {
  return (
    <motion.ul
      id="search-typeahead-listbox"
      role="listbox"
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.15 }}
      className="absolute left-0 right-0 top-full z-30 mt-1 max-h-72 overflow-auto rounded-xl border border-border bg-card/95 py-1 shadow-xl backdrop-blur-sm"
    >
      {items.map((item, index) => {
        const Icon = TYPEAHEAD_KIND_ICON[item.kind]
        const isActive = index === activeIndex
        return (
          <li key={item.id} role="presentation">
            <button
              id={item.id}
              type="button"
              role="option"
              aria-selected={isActive}
              onMouseDown={(event) => event.preventDefault()}
              onMouseEnter={() => onHover(index)}
              onClick={() => onSelect(item)}
              className={cn(
                "flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors",
                isActive ? "bg-secondary/80 text-foreground" : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground",
                item.kind === "search" && "border-t border-border/60 mt-0.5 pt-2.5",
              )}
            >
              <div
                className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                  item.kind === "agent" && "bg-violet-500/10 text-violet-400",
                  item.kind === "workflow" && "bg-amber-500/10 text-amber-400",
                  item.kind === "connector" && "bg-emerald-500/10 text-emerald-400",
                  item.kind === "history" && "bg-secondary text-muted-foreground",
                  item.kind === "search" && "bg-blue-500/10 text-blue-400",
                )}
              >
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">{item.label}</p>
                {item.subtitle ? (
                  <p className="truncate text-xs text-muted-foreground">{item.subtitle}</p>
                ) : null}
              </div>
            </button>
          </li>
        )
      })}
    </motion.ul>
  )
}

export default function ChatPage() {
  const { user } = useAuth()
  const router = useRouter()
  const { reduced, container, item } = useMotionPrefs()
  const inputRef = useRef<HTMLInputElement>(null)
  const focusSearchInput = useCallback(() => {
    inputRef.current?.focus()
  }, [])
  useWorkPageShortcut("focus-search", focusSearchInput)
  const [query, setQuery] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")
  const [typeaheadOpen, setTypeaheadOpen] = useState(false)
  const [activeTypeaheadIndex, setActiveTypeaheadIndex] = useState(-1)
  const [placeholderIndex, setPlaceholderIndex] = useState(0)
  const [inputFocused, setInputFocused] = useState(false)
  const [results, setResults] = useState<SearchResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [clearHistoryOpen, setClearHistoryOpen] = useState(false)
  const [isClearingHistory, setIsClearingHistory] = useState(false)

  useEffect(() => {
    if (user) {
      void ensureSelectedOrg()
      inputRef.current?.focus()
    }
  }, [user])

  useEffect(() => {
    if (user && consumeFocusSearchAfterNav()) {
      inputRef.current?.focus()
    }
  }, [user])

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query), 300)
    return () => window.clearTimeout(timer)
  }, [query])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "/" && !event.metaKey && !event.ctrlKey && !event.altKey) {
        const target = event.target as HTMLElement | null
        const tag = target?.tagName
        if (tag === "INPUT" || tag === "TEXTAREA" || target?.isContentEditable) return
        event.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [])

  const { data: orgContext } = useSWR(
    user ? "assistant-org-context" : null,
    () => assistantApi.orgContext(),
    { revalidateOnFocus: false },
  )

  const { data: historyData, mutate: mutateHistory } = useSWR<{ searches: SearchHistoryItem[] }>(
    user ? "/api/search/history" : null,
    apiFetcher
  )

  const history = useMemo(() => historyData?.searches ?? [], [historyData])
  const recentHistory = useMemo(() => history.slice(0, 10), [history])
  const suggestionChips = useMemo(
    () => (user ? buildOrgSearchChips(orgContext, history) : buildFallbackSearchChips()),
    [user, orgContext, history],
  )
  const searchPlaceholders = useMemo(
    () =>
      user
        ? buildSearchPlaceholders(orgContext, history)
        : buildFallbackSearchPlaceholders(),
    [user, orgContext, history],
  )
  const groupedResults = useMemo(() => groupSearchResults(results), [results])
  const typeaheadItems = useMemo(
    () =>
      user && debouncedQuery.trim()
        ? buildSearchTypeaheadItems(debouncedQuery, orgContext, history)
        : [],
    [user, debouncedQuery, orgContext, history],
  )
  const showTypeahead = Boolean(
    typeaheadOpen &&
      user &&
      query.trim().length >= 1 &&
      typeaheadItems.length > 0 &&
      !isSearching,
  )

  const typeaheadItemsKey = typeaheadItems.map((item) => item.id).join("|")
  const placeholderKey = searchPlaceholders.join("|")

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setActiveTypeaheadIndex(typeaheadItems.length > 0 ? 0 : -1)
    }, 0)
    return () => window.clearTimeout(timer)
  }, [typeaheadItemsKey, typeaheadItems.length])

  useEffect(() => {
    const timer = window.setTimeout(() => setPlaceholderIndex(0), 0)
    return () => window.clearTimeout(timer)
  }, [placeholderKey])

  useEffect(() => {
    if (query.trim() || inputFocused || searchPlaceholders.length <= 1) return
    const timer = window.setInterval(() => {
      setPlaceholderIndex((index) => (index + 1) % searchPlaceholders.length)
    }, 3000)
    return () => window.clearInterval(timer)
  }, [query, inputFocused, searchPlaceholders])

  const handleSearch = async (nextQuery?: string) => {
    if (!user) {
      toast.error("Sign in to use semantic search")
      return
    }
    const effectiveQuery = (nextQuery ?? query).trim()
    if (!effectiveQuery) return
    setQuery(effectiveQuery)
    setHasSearched(true)
    setIsSearching(true)
    try {
      const response = await searchApi.search(effectiveQuery)
      setResults(response.results)
      setSuggestions(response.suggestions)
      if (response.results.length === 0) {
        toast.message("No matches found", {
          description: "Try a shorter query or one of the suggested prompts.",
        })
      }
      await mutateHistory()
    } catch (err) {
      console.error("[v0] Search failed:", err)
      setResults([])
      toast.error("Search failed")
    } finally {
      setIsSearching(false)
    }
  }

  const selectTypeaheadItem = (item: SearchTypeaheadItem) => {
    setTypeaheadOpen(false)
    setActiveTypeaheadIndex(-1)
    if (item.href) {
      router.push(item.href)
      return
    }
    const searchText = item.searchQuery ?? item.label
    setQuery(searchText)
    void handleSearch(searchText)
  }

  const handleSampleQuery = (sample: string) => {
    setQuery(sample)
    void handleSearch(sample)
  }

  const handleNewSearch = () => {
    setHasSearched(false)
    setResults([])
    setSuggestions([])
    setQuery("")
  }

  const handleClearHistory = async () => {
    if (!user || isClearingHistory) return
    setIsClearingHistory(true)
    try {
      await searchApi.clearHistory()
      await mutateHistory()
      setClearHistoryOpen(false)
      toast.success("Search history cleared")
    } catch (err) {
      console.error("[v0] Clear history failed:", err)
      toast.error("Failed to clear history")
    } finally {
      setIsClearingHistory(false)
    }
  }

  const handleDeleteHistoryItem = async (id: string) => {
    if (!user) return
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

  const searchForm = (
    <div className="relative max-w-3xl mx-auto">
      <form onSubmit={onSubmit}>
        <div className={cn(
          "flex items-center gap-2 rounded-lg border bg-card p-2.5 pl-3 transition-all",
          "border-border hover:border-foreground/20 focus-within:border-blue-500/50 focus-within:ring-2 focus-within:ring-blue-500/20"
        )}>
          <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            role="combobox"
            aria-expanded={showTypeahead}
            aria-controls="search-typeahead-listbox"
            aria-autocomplete="list"
            aria-activedescendant={
              showTypeahead && activeTypeaheadIndex >= 0
                ? typeaheadItems[activeTypeaheadIndex]?.id
                : undefined
            }
            onChange={(event) => {
              setQuery(event.target.value)
              setTypeaheadOpen(true)
            }}
            onFocus={() => {
              setInputFocused(true)
              setTypeaheadOpen(true)
            }}
            onBlur={() => {
              setInputFocused(false)
              window.setTimeout(() => setTypeaheadOpen(false), 120)
            }}
            onKeyDown={(event) => {
              if (!showTypeahead || typeaheadItems.length === 0) return
              if (event.key === "ArrowDown") {
                event.preventDefault()
                setActiveTypeaheadIndex((index) =>
                  Math.min(index + 1, typeaheadItems.length - 1),
                )
              } else if (event.key === "ArrowUp") {
                event.preventDefault()
                setActiveTypeaheadIndex((index) => Math.max(index - 1, 0))
              } else if (event.key === "Enter" && activeTypeaheadIndex >= 0) {
                event.preventDefault()
                selectTypeaheadItem(typeaheadItems[activeTypeaheadIndex])
              } else if (event.key === "Escape") {
                event.preventDefault()
                setTypeaheadOpen(false)
                setActiveTypeaheadIndex(-1)
              }
            }}
            placeholder={searchPlaceholders[placeholderIndex] ?? searchPlaceholders[0]}
            disabled={!user || isSearching}
            className="min-w-0 flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none"
          />
          {query.trim() ? (
            <button
              type="button"
              onClick={() => {
                setQuery("")
                inputRef.current?.focus()
              }}
              disabled={isSearching}
              className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              aria-label="Clear search"
            >
              <X className="h-4 w-4" />
            </button>
          ) : null}
          <kbd className="hidden sm:inline-flex items-center gap-0.5 rounded border border-border bg-secondary/80 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
            <Command className="h-3 w-3" />
            K
          </kbd>
          <Button
            type="submit"
            size="sm"
            disabled={!user || !query.trim() || isSearching}
            className={cn(
              "gap-2 transition-transform duration-150 active:scale-90",
              query.trim() && !isSearching && "motion-safe:hover:scale-105",
            )}
          >
            {isSearching ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Search className="h-4 w-4" />
            )}
          </Button>
        </div>
        {user && suggestions.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => void handleSearch(suggestion)}
                className="rounded border border-border bg-secondary/40 px-2 py-1 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground"
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
      </form>
      <AnimatePresence>
        {showTypeahead ? (
          <SearchTypeaheadDropdown
            items={typeaheadItems}
            activeIndex={activeTypeaheadIndex}
            onHover={setActiveTypeaheadIndex}
            onSelect={selectTypeaheadItem}
          />
        ) : null}
      </AnimatePresence>
    </div>
  )

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
              <div className="text-xs text-muted-foreground shrink-0 tabular-nums">
                <AnimatedCounter value={results.length} duration={0.6} /> result{results.length === 1 ? "" : "s"}
              </div>
            </div>
          </div>

          <div className="sticky top-0 z-20 border-b border-border bg-background/95 px-4 py-3 backdrop-blur-sm md:px-6">
            {searchForm}
          </div>

          <div className="flex-1 overflow-auto p-4 md:p-6">
            <div className="max-w-3xl mx-auto space-y-4">
              {!user ? (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex flex-col items-center justify-center py-16 text-center"
                >
                  <div className="h-20 w-20 rounded-full bg-gradient-to-br from-blue-500/20 to-violet-500/20 flex items-center justify-center mb-6">
                    <Search className="h-8 w-8 text-blue-400" />
                  </div>
                  <h2 className="text-lg font-semibold text-foreground mb-2">Sign in required</h2>
                  <p className="text-sm text-muted-foreground max-w-md">
                    Semantic search and search history are available after authentication.
                  </p>
                </motion.div>
              ) : !hasSearched && !isSearching ? (
                <motion.div 
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex flex-col items-center justify-center py-16 text-center"
                >
                  <div className="relative mb-6">
                    <motion.div
                      className="h-20 w-20 rounded-full bg-gradient-to-br from-emerald-500/20 to-teal-500/20 flex items-center justify-center"
                      animate={reduced ? undefined : { y: [0, -6, 0] }}
                      transition={
                        reduced
                          ? undefined
                          : { duration: 3.2, repeat: Infinity, ease: "easeInOut" }
                      }
                    >
                      <Sparkles className="h-8 w-8 text-emerald-400" />
                    </motion.div>
                    {!reduced && (
                      <motion.div
                        className="absolute inset-0 rounded-full border-2 border-emerald-500/30"
                        animate={{ scale: [1, 1.2, 1], opacity: [0.5, 0, 0.5] }}
                        transition={{ duration: 3, repeat: Infinity }}
                      />
                    )}
                  </div>
                  <h2 className="text-lg font-semibold text-foreground mb-2">
                    What do you want to find?
                  </h2>
                  <p className="text-sm text-muted-foreground mb-6 max-w-md">
                    Use natural language to search your workflows, runs, connectors, agents, and documents.
                  </p>

                  {/* Worked query patterns — teach phrasing + what each returns */}
                  <div className="mb-6 grid w-full max-w-xl gap-3 sm:grid-cols-2">
                    {SEARCH_QUERY_PATTERNS.map((pattern) => (
                      <button
                        key={pattern.query}
                        type="button"
                        disabled={isSearching}
                        onClick={() => handleSampleQuery(pattern.query)}
                        className={cn(
                          "group flex flex-col gap-1.5 rounded-xl border border-border bg-card/50 p-4 text-left transition-colors",
                          "hover:border-foreground/20 hover:bg-card",
                          isSearching && "pointer-events-none opacity-60",
                        )}
                      >
                        <span className="flex items-center gap-2 text-sm font-medium text-foreground">
                          <pattern.icon className="h-4 w-4 shrink-0 text-primary" />
                          <span className="truncate">{`"${pattern.query}"`}</span>
                        </span>
                        <span className="text-xs leading-relaxed text-muted-foreground">{pattern.returns}</span>
                      </button>
                    ))}
                  </div>

                  <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground/70">
                    Or try
                  </p>
                  <SearchSuggestionChips
                    chips={suggestionChips}
                    reduced={reduced}
                    disabled={isSearching}
                    onSelect={handleSampleQuery}
                  />
                  <p className="mt-6 text-xs text-muted-foreground/80">
                    Pro tip: Press{" "}
                    <kbd className="rounded border border-border bg-secondary/80 px-1.5 py-0.5 font-mono text-[10px]">
                      /
                    </kbd>{" "}
                    anywhere to focus search
                    <span className="hidden sm:inline">
                      {" "}
                      ·{" "}
                      <kbd className="rounded border border-border bg-secondary/80 px-1.5 py-0.5 font-mono text-[10px]">
                        ⌘K
                      </kbd>{" "}
                      also works
                    </span>
                  </p>
                </motion.div>
              ) : (
                <>
                  <div className="flex items-center justify-between gap-3 mb-2">
                    <p className="text-sm text-muted-foreground truncate">
                      Results for <span className="text-foreground font-medium">&ldquo;{query}&rdquo;</span>
                    </p>
                    <Button variant="ghost" size="sm" type="button" onClick={handleNewSearch}>
                      New search
                    </Button>
                  </div>
                  {isSearching && (
                    <div className="space-y-3" aria-label="Searching" aria-busy="true">
                      {[0, 1, 2].map((i) => (
                        <div
                          key={i}
                          className="relative overflow-hidden rounded-xl border border-border bg-card p-4"
                        >
                          <div className="space-y-2">
                            <div className="h-2.5 w-20 rounded bg-secondary" />
                            <div className="h-3.5 w-2/3 rounded bg-secondary" />
                            <div className="h-3 w-full rounded bg-secondary/60" />
                          </div>
                          {!reduced && (
                            <motion.span
                              aria-hidden="true"
                              className="absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-foreground/10 to-transparent"
                              animate={{ x: ["-120%", "320%"] }}
                              transition={{ duration: 1.3, repeat: Infinity, ease: "easeInOut", delay: i * 0.15 }}
                            />
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                  {!isSearching && results.length === 0 && (
                    <div className="rounded-xl border border-dashed border-border bg-card/40 p-8 text-center">
                      <p className="text-sm font-medium text-foreground mb-1">No matches found</p>
                      <p className="text-sm text-muted-foreground mb-4">
                        Try refining your query or pick another prompt below.
                      </p>
                      <SearchSuggestionChips
                        chips={suggestionChips}
                        reduced={reduced}
                        disabled={isSearching}
                        onSelect={handleSampleQuery}
                      />
                    </div>
                  )}
                  {!isSearching && results.length > 0 && (
                    <motion.div
                      variants={container}
                      initial="initial"
                      animate="animate"
                      className="space-y-8"
                    >
                      {groupedResults.map((group) => (
                        <section key={group.key}>
                          <div className="mb-3 flex items-center gap-3">
                            <div className="flex items-center gap-2 shrink-0">
                              <group.icon className="h-3.5 w-3.5 text-muted-foreground" />
                              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                {group.label} ({group.items.length})
                              </h3>
                            </div>
                            <div className="h-px flex-1 bg-border" />
                          </div>
                          <AnimatePresence initial={false}>
                            <div className="space-y-2">
                              {group.items.map((result) => (
                                <SearchResultRow
                                  key={`${group.key}-${result.id}`}
                                  result={result}
                                  reduced={reduced}
                                  motionVariant={item}
                                />
                              ))}
                            </div>
                          </AnimatePresence>
                        </section>
                      ))}
                    </motion.div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        <div className="hidden lg:flex w-72 border-l border-border bg-card/30 flex-col">
          <div className="p-4 border-b border-border flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <Clock className="h-4 w-4 text-muted-foreground shrink-0" />
              <h2 className="text-sm font-semibold text-foreground truncate">Recent Searches</h2>
              {recentHistory.length > 0 && (
                <span className="rounded-full bg-secondary px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-muted-foreground">
                  {recentHistory.length}
                </span>
              )}
            </div>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 shrink-0"
                  onClick={() => setClearHistoryOpen(true)}
                  disabled={!user || recentHistory.length === 0}
                  aria-label="Clear all search history"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">Clear all history</TooltipContent>
            </Tooltip>
          </div>
          
          <div className="flex-1 overflow-auto p-2">
            {!user ? (
              <div className="flex flex-col items-center justify-center py-12 text-center px-4">
                <Clock className="h-8 w-8 text-muted-foreground/30 mb-3" />
                <p className="text-xs text-muted-foreground">Sign in to view search history</p>
              </div>
            ) : recentHistory.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center px-4">
                <motion.div
                  animate={reduced ? undefined : { y: [0, -4, 0] }}
                  transition={
                    reduced
                      ? undefined
                      : { duration: 2.8, repeat: Infinity, ease: "easeInOut" }
                  }
                  className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-secondary/80"
                >
                  <Clock className="h-5 w-5 text-muted-foreground/50" />
                </motion.div>
                <p className="text-xs font-medium text-muted-foreground">No searches yet</p>
                <p className="mt-1 text-[11px] text-muted-foreground/70">
                  Your last 10 searches will appear here
                </p>
              </div>
            ) : (
              <motion.div variants={container} initial="initial" animate="animate" className="space-y-1">
                <AnimatePresence initial={false}>
                {recentHistory.map((entry) => {
                  const isActive = hasSearched && query.trim() === entry.query.trim()
                  const relativeTime = formatRelativeTime(entry.created_at)
                  return (
                  <motion.button
                    key={entry.id}
                    variants={item}
                    layout={!reduced}
                    exit={reduced ? { opacity: 0 } : { opacity: 0, x: -12, height: 0 }}
                    type="button"
                    onClick={() => {
                      setQuery(entry.query)
                      void handleSearch(entry.query)
                    }}
                    className={cn(
                      "group w-full rounded-lg border p-2.5 text-left transition-colors",
                      isActive
                        ? "border-blue-500/30 bg-blue-500/5"
                        : "border-transparent hover:border-border/60 hover:bg-secondary/50",
                    )}
                  >
                    <div className="flex items-start gap-2.5">
                      <Search className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground group-hover:text-blue-400 transition-colors" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-foreground group-hover:text-blue-400 transition-colors">
                          {entry.query}
                        </p>
                        <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
                          {relativeTime ? <span>{relativeTime}</span> : null}
                          <span
                            className={cn(
                              "rounded-full px-1.5 py-0.5 tabular-nums",
                              entry.results_count > 0
                                ? "bg-emerald-500/10 text-emerald-500"
                                : "bg-secondary text-muted-foreground",
                            )}
                          >
                            {entry.results_count} result{entry.results_count === 1 ? "" : "s"}
                          </span>
                        </div>
                      </div>
                      <span
                        role="button"
                        tabIndex={0}
                        aria-label={`Remove "${entry.query}" from history`}
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
                        className="rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-secondary hover:text-foreground group-hover:opacity-100 focus:opacity-100"
                      >
                        <X className="h-3.5 w-3.5" />
                      </span>
                    </div>
                  </motion.button>
                  )
                })}
                </AnimatePresence>
              </motion.div>
            )}
          </div>
        </div>

        <AlertDialog open={clearHistoryOpen} onOpenChange={setClearHistoryOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Clear search history?</AlertDialogTitle>
              <AlertDialogDescription>
                This removes all {recentHistory.length} recent searches from your history. This cannot be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={isClearingHistory}>Cancel</AlertDialogCancel>
              <AlertDialogAction
                disabled={isClearingHistory}
                className="bg-red-500 hover:bg-red-600"
                onClick={(event) => {
                  event.preventDefault()
                  void handleClearHistory()
                }}
              >
                {isClearingHistory ? "Clearing..." : "Clear history"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </AppShell>
  )
}
