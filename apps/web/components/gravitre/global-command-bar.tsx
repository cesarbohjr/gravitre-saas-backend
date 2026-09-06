"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { Icon, type IconName } from "@/lib/icons"
import { APP_ROUTES } from "@/lib/app-routes"
import { cn } from "@/lib/utils"
import { useViewModeSafe } from "@/lib/view-mode-context"
import { PulseDot } from "@/components/gravitre/visual"

interface CommandItem {
  id: string
  type: "navigation" | "action" | "ai" | "recent"
  title: string
  subtitle?: string
  icon: IconName
  href?: string
  action?: () => void
  keywords?: string[]
  /** A1: omit from command palette for Lite seats (BUILD surfaces). */
  requiresFullSeat?: boolean
}

const navigationItems: CommandItem[] = [
  {
    id: "nav-ai",
    type: "navigation",
    title: "Chat",
    subtitle: "Unified execute, chat, and find",
    icon: "chat",
    href: APP_ROUTES.gravitreAi,
    keywords: ["ai", "execute", "task", "delegate", "chat", "find"],
  },
  {
    id: "nav-assistant",
    type: "navigation",
    title: "Workspace Chat",
    subtitle: "Multi-turn chat with tools",
    icon: "chat",
    href: `${APP_ROUTES.gravitreAi}?mode=chat`,
    keywords: ["assistant", "chat", "conversation", "help"],
  },
  {
    id: "nav-search",
    type: "navigation",
    title: "Universal Search",
    subtitle: "Find workflows, runs, and docs",
    icon: "search",
    href: "/search",
    keywords: ["search", "find", "query", "records"],
  },
  { id: "nav-agents", type: "navigation", title: "Agents", subtitle: "AI agents", icon: "agents", href: "/agents", keywords: ["bot", "automation"], requiresFullSeat: true },
  { id: "nav-workflows", type: "navigation", title: "Workflows", subtitle: "Automation flows", icon: "automations", href: "/workflows", keywords: ["flow", "pipeline"], requiresFullSeat: true },
  { id: "nav-connectors", type: "navigation", title: "Connectors", subtitle: "Integrations", icon: "apps", href: "/connectors", keywords: ["api", "integration"], requiresFullSeat: true },
  { id: "nav-sources", type: "navigation", title: "Sources", subtitle: "Data sources", icon: "data", href: "/sources", keywords: ["data", "database"], requiresFullSeat: true },
  { id: "nav-assign", type: "navigation", title: "Assign Work", subtitle: "Run department workflows", icon: "send", href: "/lite/assign", keywords: ["assign", "lite", "work"] },
  { id: "nav-tasks", type: "navigation", title: "My Tasks", subtitle: "Assigned work", icon: "listTodo", href: "/lite/tasks", keywords: ["tasks", "lite"] },
  { id: "nav-activity", type: "navigation", title: "Activity", subtitle: "Completed work and failure alerts", icon: "run", href: "/activity", keywords: ["execute", "history", "runs", "outcomes"] },
  { id: "nav-approvals", type: "navigation", title: "Approvals", subtitle: "Pending reviews", icon: "approvals", href: "/approvals", keywords: ["review", "approve"] },
  { id: "nav-intelligence", type: "navigation", title: "Intelligence", subtitle: "Health, ROI, learning, models", icon: "dashboard", href: "/intelligence", keywords: ["monitor", "stats", "metrics", "insights"] },
  { id: "nav-audit", type: "navigation", title: "Audit Log", subtitle: "Compliance export", icon: "history", href: "/audit", keywords: ["log", "history", "compliance"] },
  { id: "nav-settings", type: "navigation", title: "Settings", subtitle: "Personal, organization, admin", icon: "settings", href: "/settings", keywords: ["config", "preferences", "enterprise", "federation", "environments"] },
]

const aiCommands: CommandItem[] = [
  { id: "ai-analyze", type: "ai", title: "Analyze pipeline failures", subtitle: "AI investigation", icon: "error", keywords: ["debug", "error", "failure"] },
  { id: "ai-broken", type: "ai", title: "Find broken workflows", subtitle: "AI scan", icon: "bug", keywords: ["broken", "issue", "problem"] },
  { id: "ai-performance", type: "ai", title: "Analyze system performance", subtitle: "AI analysis", icon: "chartLine", keywords: ["performance", "slow", "latency"] },
  { id: "ai-optimize", type: "ai", title: "Suggest optimizations", subtitle: "AI recommendations", icon: "execution", keywords: ["optimize", "improve", "speed"] },
  { id: "ai-agent", type: "ai", title: "Run marketing agent", subtitle: "Execute agent", icon: "agents", keywords: ["run", "agent", "marketing"] },
]

// Do not ship hard-coded demo "recent" rows — they look clickable but are mocks
// (Prompt3 click-audit: dead/misleading affordances). Real recents should come
// from conversation/run history when wired; until then keep this empty.
const recentItems: CommandItem[] = []

export function GlobalCommandBar() {
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [selectedIndex, setSelectedIndex] = useState(0)
  const router = useRouter()
  const viewMode = useViewModeSafe()
  const isLite = Boolean(viewMode?.isLite)

  // Filter items based on query
  const filteredItems = useCallback(() => {
    const q = query.toLowerCase().trim()
    const navForSeat = navigationItems.filter((item) => {
      if (isLite && item.requiresFullSeat) return false
      if (!isLite && (item.id === "nav-assign" || item.id === "nav-tasks")) return false
      return true
    })

    if (!q) {
      // Show recent + AI commands when empty
      return [
        { group: "Recent", items: recentItems },
        { group: "AI Commands", items: isLite ? [] : aiCommands.slice(0, 3) },
        { group: "Navigation", items: navForSeat.slice(0, 5) },
      ]
    }

    const matchItem = (item: CommandItem) => {
      const titleMatch = item.title.toLowerCase().includes(q)
      const subtitleMatch = item.subtitle?.toLowerCase().includes(q)
      const keywordMatch = item.keywords?.some(k => k.includes(q))
      return titleMatch || subtitleMatch || keywordMatch
    }

    const matchedAI = isLite ? [] : aiCommands.filter(matchItem)
    const matchedNav = navForSeat.filter(matchItem)
    const matchedRecent = recentItems.filter(matchItem)

    const groups = []
    if (matchedAI.length > 0) groups.push({ group: "AI Commands", items: matchedAI })
    if (matchedNav.length > 0) groups.push({ group: "Navigation", items: matchedNav })
    if (matchedRecent.length > 0) groups.push({ group: "Recent", items: matchedRecent })
    
    return groups
  }, [query, isLite])

  const groups = filteredItems()
  const allItems = groups.flatMap(g => g.items)

  // ⌘K is handled globally by CommandPalette in AppShell.

  useEffect(() => {
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsOpen(false)
      }
    }
    window.addEventListener("keydown", onEscape)
    return () => window.removeEventListener("keydown", onEscape)
  }, [])

  // Handle navigation within list
  const handleSelect = (item: CommandItem) => {
    if (item.href) {
      router.push(item.href)
    } else if (item.action) {
      item.action()
    } else if (item.type === "ai") {
      // Navigate to operator with the query
      router.push(`${APP_ROUTES.gravitreAi}?prompt=${encodeURIComponent(item.title)}`)
    }
    setIsOpen(false)
    setQuery("")
  }

  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault()
        setSelectedIndex(prev => Math.min(prev + 1, allItems.length - 1))
      }
      if (e.key === "ArrowUp") {
        e.preventDefault()
        setSelectedIndex(prev => Math.max(prev - 1, 0))
      }
      if (e.key === "Enter" && allItems[selectedIndex]) {
        e.preventDefault()
        handleSelect(allItems[selectedIndex])
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [isOpen, selectedIndex, allItems])

  const getItemIndex = (item: CommandItem) => {
    return allItems.findIndex(i => i.id === item.id)
  }

  return (
    <>
      {/* Trigger Button - Premium */}
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        aria-label="Search or run a command"
        className="group flex h-11 items-center justify-center gap-2 rounded-full border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-2)] px-3 text-sm text-[color:var(--g-text-muted)] transition-colors hover:border-[color:var(--g-border-active)] hover:bg-[color:var(--g-surface-3)] hover:text-[color:var(--g-text-primary)] sm:h-8 sm:px-3.5"
      >
        <Icon name="search" size="sm" className="shrink-0" />
        <span className="hidden lg:inline font-medium">Search or command...</span>
        <kbd className="ml-1 hidden items-center gap-0.5 rounded-md border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] px-2 py-0.5 font-mono text-[10px] text-[color:var(--g-text-muted)] lg:inline-flex">
          <Icon name="command" size="xs" />K
        </kbd>
      </button>

      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="fixed inset-0 z-50 bg-[color:var(--g-text-primary)]/35 backdrop-blur-sm"
              onClick={() => setIsOpen(false)}
            />

            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18, ease: [0.4, 0, 0.2, 1] }}
              className="fixed left-1/2 top-[18%] z-50 w-full max-w-2xl -translate-x-1/2 px-4"
            >
              <div
                className="g-material-panel relative overflow-hidden rounded-[var(--g-radius-panel)] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-elevated)] shadow-[var(--g-shadow-elevated)]"
              >
                <div className="relative flex items-center gap-3 border-b border-[color:var(--g-border-subtle)] px-4 py-3">
                  <Icon name="search" size="md" className="shrink-0 text-[color:var(--g-text-muted)]" />
                  <input
                    type="text"
                    value={query}
                    onChange={(e) => {
                      setQuery(e.target.value)
                      setSelectedIndex(0)
                    }}
                    placeholder="Search commands, navigate, or ask AI..."
                    autoFocus
                    className="flex-1 bg-transparent text-sm text-[color:var(--g-text-primary)] placeholder:text-[color:var(--g-text-muted)] focus:outline-none"
                  />
                  {query ? <PulseDot tone="intelligence" size="sm" label="Filtering" /> : null}
                  <kbd className="shrink-0 rounded-md border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-2)] px-2 py-0.5 font-mono text-[10px] text-[color:var(--g-text-muted)]">
                    ESC
                  </kbd>
                </div>

                <div className="relative max-h-[420px] overflow-y-auto p-2 scrollbar-on-hover">
                  {groups.length === 0 ? (
                    <div className="px-4 py-10 text-center">
                      <Icon name="search" size="xl" className="mx-auto mb-3 text-[color:var(--g-text-muted)] opacity-40" />
                      <p className="text-sm text-[color:var(--g-text-secondary)]">
                        No results found for &ldquo;{query}&rdquo;
                      </p>
                      <p className="mt-1 text-xs text-[color:var(--g-text-muted)]">
                        Try different keywords
                      </p>
                    </div>
                  ) : (
                    <div>
                      {groups.map((group) => (
                        <div key={group.group} className="mb-2">
                          <div className="flex items-center gap-2 px-3 py-1.5">
                            <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[color:var(--g-text-muted)]">
                              {group.group}
                            </span>
                          </div>
                          <div className="space-y-0.5">
                            {group.items.map((item) => {
                              const index = getItemIndex(item)
                              const isSelected = index === selectedIndex
                              return (
                                <button
                                  type="button"
                                  key={item.id}
                                  onClick={() => handleSelect(item)}
                                  onMouseEnter={() => setSelectedIndex(index)}
                                  className={cn(
                                    "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors",
                                    isSelected
                                      ? "bg-[color:var(--g-surface-active)] text-[color:var(--g-text-primary)]"
                                      : "text-[color:var(--g-text-secondary)] hover:bg-[color:var(--g-surface-2)]",
                                  )}
                                >
                                  <Icon
                                    name={item.icon}
                                    size="md"
                                    className={cn(
                                      "shrink-0",
                                      isSelected
                                        ? "text-[color:var(--g-intelligence)]"
                                        : "text-[color:var(--g-text-muted)]",
                                    )}
                                  />
                                  <div className="min-w-0 flex-1">
                                    <div className="truncate text-sm font-medium">{item.title}</div>
                                    {item.subtitle ? (
                                      <div className="truncate text-xs text-[color:var(--g-text-muted)]">
                                        {item.subtitle}
                                      </div>
                                    ) : null}
                                  </div>
                                </button>
                              )
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between border-t border-[color:var(--g-border-subtle)] px-4 py-2 text-[10px] text-[color:var(--g-text-muted)]">
                  <span>Navigate</span>
                  <span>Enter to select · Esc to close</span>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
