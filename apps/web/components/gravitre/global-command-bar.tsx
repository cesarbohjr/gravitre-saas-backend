"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { Icon, type IconName } from "@/lib/icons"
import {
  GlowOrb,
  NeuralNetwork,
  StatusBeacon,
  DataStream
} from "@/components/gravitre/premium-effects"
import { cn } from "@/lib/utils"

interface CommandItem {
  id: string
  type: "navigation" | "action" | "ai" | "recent"
  title: string
  subtitle?: string
  icon: IconName
  href?: string
  action?: () => void
  keywords?: string[]
}

const navigationItems: CommandItem[] = [
  { id: "nav-operator", type: "navigation", title: "AI Assistant", subtitle: "Command center", icon: "ai", href: "/operator", keywords: ["ai", "analyze", "debug"] },
  { id: "nav-search", type: "navigation", title: "Knowledge Search", subtitle: "Search data", icon: "search", href: "/chat", keywords: ["search", "find", "query"] },
  { id: "nav-agents", type: "navigation", title: "Agents", subtitle: "AI agents", icon: "agents", href: "/agents", keywords: ["bot", "automation"] },
  { id: "nav-workflows", type: "navigation", title: "Workflows", subtitle: "Automation flows", icon: "automations", href: "/workflows", keywords: ["flow", "pipeline"] },
  { id: "nav-connectors", type: "navigation", title: "Connectors", subtitle: "Integrations", icon: "apps", href: "/connectors", keywords: ["api", "integration"] },
  { id: "nav-sources", type: "navigation", title: "Sources", subtitle: "Data sources", icon: "data", href: "/sources", keywords: ["data", "database"] },
  { id: "nav-runs", type: "navigation", title: "Runs", subtitle: "Execution history", icon: "run", href: "/runs", keywords: ["execute", "history"] },
  { id: "nav-approvals", type: "navigation", title: "Approvals", subtitle: "Pending reviews", icon: "approvals", href: "/approvals", keywords: ["review", "approve"] },
  { id: "nav-metrics", type: "navigation", title: "Metrics", subtitle: "Monitoring", icon: "dashboard", href: "/metrics", keywords: ["monitor", "stats"] },
  { id: "nav-audit", type: "navigation", title: "Audit Log", subtitle: "Activity history", icon: "history", href: "/audit", keywords: ["log", "history"] },
  { id: "nav-environments", type: "navigation", title: "Environments", subtitle: "Production & staging", icon: "workspaces", href: "/environments", keywords: ["prod", "staging"] },
  { id: "nav-settings", type: "navigation", title: "Settings", subtitle: "Configuration", icon: "settings", href: "/settings", keywords: ["config", "preferences"] },
]

const aiCommands: CommandItem[] = [
  { id: "ai-analyze", type: "ai", title: "Analyze pipeline failures", subtitle: "AI investigation", icon: "error", keywords: ["debug", "error", "failure"] },
  { id: "ai-broken", type: "ai", title: "Find broken workflows", subtitle: "AI scan", icon: "bug", keywords: ["broken", "issue", "problem"] },
  { id: "ai-performance", type: "ai", title: "Analyze system performance", subtitle: "AI analysis", icon: "chartLine", keywords: ["performance", "slow", "latency"] },
  { id: "ai-optimize", type: "ai", title: "Suggest optimizations", subtitle: "AI recommendations", icon: "execution", keywords: ["optimize", "improve", "speed"] },
  { id: "ai-agent", type: "ai", title: "Run marketing agent", subtitle: "Execute agent", icon: "agents", keywords: ["run", "agent", "marketing"] },
]

const recentItems: CommandItem[] = [
  { id: "recent-1", type: "recent", title: "Investigating failed customer sync", subtitle: "2 minutes ago", icon: "pending", href: "/operator" },
  { id: "recent-2", type: "recent", title: "sync-customers-1234", subtitle: "Workflow run", icon: "run", href: "/runs/sync-customers-1234" },
]

export function GlobalCommandBar() {
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [selectedIndex, setSelectedIndex] = useState(0)
  const router = useRouter()

  // Filter items based on query
  const filteredItems = useCallback(() => {
    const q = query.toLowerCase().trim()
    
    if (!q) {
      // Show recent + AI commands when empty
      return [
        { group: "Recent", items: recentItems },
        { group: "AI Commands", items: aiCommands.slice(0, 3) },
        { group: "Navigation", items: navigationItems.slice(0, 5) },
      ]
    }

    const matchItem = (item: CommandItem) => {
      const titleMatch = item.title.toLowerCase().includes(q)
      const subtitleMatch = item.subtitle?.toLowerCase().includes(q)
      const keywordMatch = item.keywords?.some(k => k.includes(q))
      return titleMatch || subtitleMatch || keywordMatch
    }

    const matchedAI = aiCommands.filter(matchItem)
    const matchedNav = navigationItems.filter(matchItem)
    const matchedRecent = recentItems.filter(matchItem)

    const groups = []
    if (matchedAI.length > 0) groups.push({ group: "AI Commands", items: matchedAI })
    if (matchedNav.length > 0) groups.push({ group: "Navigation", items: matchedNav })
    if (matchedRecent.length > 0) groups.push({ group: "Recent", items: matchedRecent })
    
    return groups
  }, [query])

  const groups = filteredItems()
  const allItems = groups.flatMap(g => g.items)

  // Keyboard shortcut to open
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        setIsOpen(prev => !prev)
      }
      if (e.key === "Escape") {
        setIsOpen(false)
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [])

  // Handle navigation within list
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

  // Reset selection when query changes
  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  const handleSelect = (item: CommandItem) => {
    if (item.href) {
      router.push(item.href)
    } else if (item.action) {
      item.action()
    } else if (item.type === "ai") {
      // Navigate to operator with the query
      router.push(`/operator?prompt=${encodeURIComponent(item.title)}`)
    }
    setIsOpen(false)
    setQuery("")
  }

  const getItemIndex = (item: CommandItem) => {
    return allItems.findIndex(i => i.id === item.id)
  }

  return (
    <>
      {/* Trigger Button - Premium */}
      <motion.button
        onClick={() => setIsOpen(true)}
        className="group relative flex items-center gap-2 rounded-xl border border-border/60 bg-secondary/50 px-3.5 py-2 text-sm text-muted-foreground transition-all hover:border-primary/30 hover:bg-secondary/80 hover:text-foreground hover:shadow-lg hover:shadow-primary/5 backdrop-blur-sm overflow-hidden"
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
      >
        {/* Hover glow effect */}
        <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 bg-gradient-to-r from-primary/5 via-primary/10 to-primary/5" />
        <motion.div
          className="relative z-10 flex items-center gap-2"
        >
          <div className="relative">
            <Icon name="search" size="sm" className="transition-colors group-hover:text-primary" />
            <div className="absolute inset-0 blur-sm group-hover:bg-primary/30 transition-all opacity-0 group-hover:opacity-100" />
          </div>
          <span className="hidden sm:inline font-medium">Search or command...</span>
          <kbd className="ml-1 hidden rounded-md bg-background/80 border border-border/50 px-2 py-0.5 font-mono text-[10px] text-muted-foreground sm:inline-flex items-center gap-0.5 group-hover:border-primary/30 transition-colors">
            <Icon name="command" size="xs" />K
          </kbd>
        </motion.div>
      </motion.button>

      {/* Modal - Premium */}
      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop with premium effects */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md"
              onClick={() => setIsOpen(false)}
            >
              {/* Ambient orbs in backdrop */}
              <div className="absolute top-1/4 left-1/4 pointer-events-none">
                <GlowOrb size={300} color="violet" intensity={0.15} />
              </div>
              <div className="absolute bottom-1/4 right-1/4 pointer-events-none">
                <GlowOrb size={250} color="blue" intensity={0.1} />
              </div>
            </motion.div>

            {/* Command Panel - Premium */}
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: -30 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: -20 }}
              transition={{ type: "spring", stiffness: 300, damping: 25 }}
              className="fixed left-1/2 top-[18%] z-50 w-full max-w-2xl -translate-x-1/2 px-4"
            >
              <div className="relative overflow-hidden rounded-3xl border border-border/40 bg-popover/95 backdrop-blur-xl shadow-2xl shadow-black/50">
                {/* Top gradient accent */}
                <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-violet-500 via-blue-500 to-violet-500" />
                
                {/* Corner glow */}
                <div className="absolute -top-20 -right-20 w-40 h-40 pointer-events-none">
                  <GlowOrb size={160} color="blue" intensity={0.2} />
                </div>
                {/* Input - Premium */}
                <div className="relative flex items-center gap-4 border-b border-border/30 px-5 py-4 bg-gradient-to-r from-transparent via-card/50 to-transparent">
                  {/* AI icon with glow */}
                  <motion.div 
                    className="relative shrink-0"
                    animate={{ scale: [1, 1.05, 1] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    <Icon name="ai" size="lg" className="text-info relative z-10" emphasis />
                    <div className="absolute inset-0 blur-md bg-info/40" />
                  </motion.div>
                  
                  <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search commands, navigate, or ask AI..."
                    autoFocus
                    className="flex-1 bg-transparent text-base text-foreground placeholder:text-muted-foreground/50 focus:outline-none font-medium"
                  />
                  
                  {/* Live typing indicator */}
                  {query && (
                    <motion.div
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      className="shrink-0"
                    >
                      <StatusBeacon status="processing" size="sm" pulse />
                    </motion.div>
                  )}
                  
                  <kbd className="shrink-0 rounded-lg bg-secondary/80 border border-border/50 px-2.5 py-1 font-mono text-[10px] text-muted-foreground">
                    ESC
                  </kbd>
                </div>

                {/* Results - Premium */}
                <div className="relative max-h-[420px] overflow-y-auto p-3 scrollbar-on-hover">
                  {groups.length === 0 ? (
                    <motion.div 
                      className="px-4 py-12 text-center"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                    >
                      <Icon name="search" size="xl" className="text-muted-foreground/30 mx-auto mb-3" />
                      <p className="text-sm text-muted-foreground">
                        No results found for &ldquo;{query}&rdquo;
                      </p>
                      <p className="text-xs text-muted-foreground/60 mt-1">
                        Try different keywords or ask AI for help
                      </p>
                    </motion.div>
                  ) : (
                    <AnimatePresence mode="popLayout">
                      {groups.map((group, groupIndex) => (
                        <motion.div 
                          key={group.group} 
                          className="mb-3"
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: groupIndex * 0.05 }}
                        >
                          <div className="flex items-center gap-2 px-3 py-2">
                            <div className="h-px flex-1 bg-gradient-to-r from-border to-transparent" />
                            <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/50">
                              {group.group}
                            </span>
                            <div className="h-px flex-1 bg-gradient-to-l from-border to-transparent" />
                          </div>
                          <div className="space-y-1">
                            {group.items.map((item, itemIndex) => {
                              const index = getItemIndex(item)
                              const isSelected = index === selectedIndex
                              return (
                                <motion.button
                                  key={item.id}
                                  onClick={() => handleSelect(item)}
                                  onMouseEnter={() => setSelectedIndex(index)}
                                  initial={{ opacity: 0, x: -10 }}
                                  animate={{ opacity: 1, x: 0 }}
                                  transition={{ delay: (groupIndex * 0.05) + (itemIndex * 0.02) }}
                                  className={cn(
                                    "flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition-all relative overflow-hidden",
                                    isSelected 
                                      ? "bg-gradient-to-r from-info/15 to-info/5 ring-1 ring-info/30 shadow-lg shadow-info/5" 
                                      : "hover:bg-secondary/60"
                                  )}
                                >
                                  {/* Selected highlight */}
                                  {isSelected && (
                                    <motion.div 
                                      className="absolute left-0 top-0 bottom-0 w-0.5 bg-info"
                                      layoutId="selectedIndicator"
                                    />
                                  )}
                                  
                                  <motion.div 
                                    className={cn(
                                      "rounded-xl p-2.5 transition-all relative",
                                      isSelected ? "bg-info/20 shadow-md shadow-info/10" : "bg-secondary/80",
                                      item.type === "ai" ? "text-info" : "text-muted-foreground"
                                    )}
                                    animate={isSelected && item.type === "ai" ? { scale: [1, 1.05, 1] } : {}}
                                    transition={{ duration: 1.5, repeat: Infinity }}
                                  >
                                    <Icon name={item.icon} size="sm" />
                                    {item.type === "ai" && isSelected && (
                                      <div className="absolute inset-0 rounded-xl blur-sm bg-info/30" />
                                    )}
                                  </motion.div>
                                  
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                      <span className={cn(
                                        "text-sm font-semibold transition-colors",
                                        isSelected ? "text-foreground" : "text-foreground/90"
                                      )}>{item.title}</span>
                                      {item.type === "ai" && (
                                        <span className="flex items-center gap-1 rounded-full bg-info/10 px-2 py-0.5 text-[9px] font-bold text-info ring-1 ring-info/20">
                                          <StatusBeacon status="active" size="sm" pulse />
                                          AI
                                        </span>
                                      )}
                                    </div>
                                    {item.subtitle && (
                                      <p className="text-xs text-muted-foreground/70 truncate mt-0.5">{item.subtitle}</p>
                                    )}
                                  </div>
                                  
                                  <motion.div
                                    animate={isSelected ? { x: [0, 3, 0] } : {}}
                                    transition={{ duration: 1, repeat: Infinity }}
                                  >
                                    <Icon name="forward" size="sm" className={cn(
                                      "transition-colors",
                                      isSelected ? "text-info" : "text-muted-foreground/20"
                                    )} />
                                  </motion.div>
                                </motion.button>
                              )
                            })}
                          </div>
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  )}
                </div>

                {/* Footer - Premium */}
                <div className="relative flex items-center justify-between border-t border-border/30 px-5 py-3 bg-gradient-to-r from-secondary/20 via-transparent to-secondary/20">
                  <div className="flex items-center gap-4">
                    <span className="flex items-center gap-1.5 text-[10px] text-muted-foreground/70">
                      <kbd className="rounded-md bg-secondary/80 border border-border/50 px-1.5 py-0.5 font-mono">↑</kbd>
                      <kbd className="rounded-md bg-secondary/80 border border-border/50 px-1.5 py-0.5 font-mono">↓</kbd>
                      <span className="ml-0.5">navigate</span>
                    </span>
                    <span className="flex items-center gap-1.5 text-[10px] text-muted-foreground/70">
                      <kbd className="rounded-md bg-secondary/80 border border-border/50 px-1.5 py-0.5 font-mono">↵</kbd>
                      <span className="ml-0.5">select</span>
                    </span>
                    <span className="flex items-center gap-1.5 text-[10px] text-muted-foreground/70">
                      <kbd className="rounded-md bg-secondary/80 border border-border/50 px-1.5 py-0.5 font-mono">Tab</kbd>
                      <span className="ml-0.5">autocomplete</span>
                    </span>
                  </div>
                  <motion.span 
                    className="flex items-center gap-1.5 text-[10px] text-muted-foreground/70"
                    animate={{ opacity: [0.6, 1, 0.6] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    <Icon name="ai" size="xs" className="text-info" emphasis />
                    <span className="font-semibold text-info/80">Gravitre AI</span>
                    <span>ready</span>
                  </motion.span>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
