"use client"

import { useState, useEffect, createContext, useContext, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Check,
  ChevronDown,
  ChevronUp,
  Circle,
  Sparkles,
  Bot,
  Plug,
  FileText,
  Users,
  Zap,
  X,
  ArrowRight,
  Rocket,
  Gift,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { useViewModeSafe } from "@/lib/view-mode-context"

// Types
interface ChecklistItem {
  id: string
  title: string
  description: string
  href: string
  icon: React.ElementType
  completed: boolean
}

interface OnboardingState {
  items: ChecklistItem[]
  dismissed: boolean
  completedAt: string | null
}

// Default checklist items
const defaultItems: ChecklistItem[] = [
  {
    id: "create-agent",
    title: "Create your first agent",
    description: "Set up an AI agent to handle tasks",
    href: "/agents/new",
    icon: Bot,
    completed: false,
  },
  {
    id: "connect-tool",
    title: "Connect a tool",
    description: "Link Slack, HubSpot, or another integration",
    href: "/connectors",
    icon: Plug,
    completed: false,
  },
  {
    id: "run-workflow",
    title: "Run your first workflow",
    description: "Create and execute an automation",
    href: "/workflows",
    icon: Zap,
    completed: false,
  },
  {
    id: "review-output",
    title: "Review an output",
    description: "Check a deliverable from your agent",
    href: "/deliverables",
    icon: FileText,
    completed: false,
  },
  {
    id: "invite-team",
    title: "Invite a teammate",
    description: "Collaborate with your team",
    href: "/settings/organizations",
    icon: Users,
    completed: false,
  },
]

// Local storage key
const STORAGE_KEY = "gravitre-onboarding"

// Map of item IDs to their icons (icons can't be serialized to localStorage)
const itemIconMap: Record<string, React.ElementType> = {
  "create-agent": Bot,
  "connect-tool": Plug,
  "run-workflow": Zap,
  "review-output": FileText,
  "invite-team": Users,
}

// Helper to reconstruct items with icons from stored state
function reconstructItemsWithIcons(storedItems: Array<{ id: string; completed: boolean }>): ChecklistItem[] {
  return defaultItems.map(defaultItem => {
    const storedItem = storedItems.find(s => s.id === defaultItem.id)
    return {
      ...defaultItem,
      icon: itemIconMap[defaultItem.id] || defaultItem.icon,
      completed: storedItem?.completed ?? defaultItem.completed,
    }
  })
}

// Context
interface OnboardingContextType {
  items: ChecklistItem[]
  completedCount: number
  totalCount: number
  progress: number
  isComplete: boolean
  isDismissed: boolean
  markComplete: (itemId: string) => void
  markIncomplete: (itemId: string) => void
  dismiss: () => void
  reset: () => void
}

const OnboardingContext = createContext<OnboardingContextType | null>(null)

export function useOnboarding() {
  const context = useContext(OnboardingContext)
  if (!context) {
    throw new Error("useOnboarding must be used within OnboardingProvider")
  }
  return context
}

// Provider
export function OnboardingProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<OnboardingState>({
    items: defaultItems,
    dismissed: false,
    completedAt: null,
  })

  // Load from localStorage
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      try {
        const parsed = JSON.parse(stored)
        // Reconstruct items with proper icon components (icons can't be serialized)
        const reconstructedItems = reconstructItemsWithIcons(
          parsed.items?.map((item: ChecklistItem) => ({ id: item.id, completed: item.completed })) || []
        )
        setState({
          ...parsed,
          items: reconstructedItems,
        })
      } catch {
        // Invalid data, use defaults
      }
    }
  }, [])

  // Save to localStorage (only save serializable data, not icon components)
  useEffect(() => {
    const serializableState = {
      items: state.items.map(item => ({ id: item.id, completed: item.completed })),
      dismissed: state.dismissed,
      completedAt: state.completedAt,
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(serializableState))
  }, [state])

  const completedCount = state.items.filter((item) => item.completed).length
  const totalCount = state.items.length
  const progress = totalCount > 0 ? (completedCount / totalCount) * 100 : 0
  const isComplete = completedCount === totalCount

  const markComplete = useCallback((itemId: string) => {
    setState((prev) => {
      const newItems = prev.items.map((item) =>
        item.id === itemId ? { ...item, completed: true } : item
      )
      const allComplete = newItems.every((item) => item.completed)
      return {
        ...prev,
        items: newItems,
        completedAt: allComplete ? new Date().toISOString() : prev.completedAt,
      }
    })
  }, [])

  const markIncomplete = useCallback((itemId: string) => {
    setState((prev) => ({
      ...prev,
      items: prev.items.map((item) =>
        item.id === itemId ? { ...item, completed: false } : item
      ),
      completedAt: null,
    }))
  }, [])

  const dismiss = useCallback(() => {
    setState((prev) => ({ ...prev, dismissed: true }))
  }, [])

  const reset = useCallback(() => {
    setState({
      items: defaultItems,
      dismissed: false,
      completedAt: null,
    })
  }, [])

  return (
    <OnboardingContext.Provider
      value={{
        items: state.items,
        completedCount,
        totalCount,
        progress,
        isComplete,
        isDismissed: state.dismissed,
        markComplete,
        markIncomplete,
        dismiss,
        reset,
      }}
    >
      {children}
    </OnboardingContext.Provider>
  )
}

// Floating Checklist Widget
export function OnboardingChecklist() {
  const pathname = usePathname()
  const { isAdmin } = useViewModeSafe()
  const {
    items,
    completedCount,
    totalCount,
    progress,
    isComplete,
    isDismissed,
    markComplete,
    dismiss,
  } = useOnboarding()
  const [isExpanded, setIsExpanded] = useState(false)
  const [showCelebration, setShowCelebration] = useState(false)

  // Hide on marketing pages and for non-admin users
  const isMarketingPage = pathname?.startsWith("/(marketing)") || 
    pathname === "/" || 
    pathname === "/login" || 
    pathname === "/pricing" ||
    pathname === "/features" ||
    pathname === "/docs" ||
    pathname === "/about" ||
    pathname === "/careers" ||
    pathname === "/contact" ||
    pathname === "/get-started" ||
    pathname?.startsWith("/blog")
  
  const hiddenPaths = ["/onboarding", "/lite"]
  const isHiddenPath = hiddenPaths.some((path) => pathname === path || pathname?.startsWith(path))
  
  // Only show for admin users in the web app, not on marketing pages or for lite users
  const shouldHide = isMarketingPage || isHiddenPath || !isAdmin

  // Show celebration when complete
  useEffect(() => {
    if (isComplete && !showCelebration) {
      setShowCelebration(true)
      const timer = setTimeout(() => setShowCelebration(false), 5000)
      return () => clearTimeout(timer)
    }
  }, [isComplete, showCelebration])

  if (shouldHide || isDismissed || (isComplete && !showCelebration)) {
    return null
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 20, scale: 0.95 }}
        className="fixed bottom-6 right-6 z-50 w-80"
      >
        {/* Celebration overlay */}
        {showCelebration && (
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            className="absolute inset-0 -m-4 rounded-3xl bg-gradient-to-br from-emerald-500/20 to-blue-500/20 blur-xl"
          />
        )}

        <div className="relative rounded-2xl border border-border bg-card shadow-xl overflow-hidden">
          {/* Header */}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="w-full p-4 flex items-center gap-3 hover:bg-secondary/50 transition-colors"
          >
            <div className="relative">
              <div
                className={cn(
                  "h-10 w-10 rounded-xl flex items-center justify-center transition-colors",
                  isComplete
                    ? "bg-emerald-500"
                    : "bg-gradient-to-br from-emerald-500/20 to-blue-500/20"
                )}
              >
                {isComplete ? (
                  <Gift className="h-5 w-5 text-white" />
                ) : (
                  <Rocket className="h-5 w-5 text-emerald-500" />
                )}
              </div>
              {/* Progress ring */}
              {!isComplete && (
                <svg
                  className="absolute inset-0 h-10 w-10 -rotate-90"
                  viewBox="0 0 40 40"
                >
                  <circle
                    cx="20"
                    cy="20"
                    r="18"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                    className="text-secondary"
                  />
                  <circle
                    cx="20"
                    cy="20"
                    r="18"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                    strokeDasharray={`${progress * 1.13} 113`}
                    className="text-emerald-500 transition-all duration-500"
                    strokeLinecap="round"
                  />
                </svg>
              )}
            </div>
            <div className="flex-1 text-left">
              <p className="text-sm font-medium text-foreground">
                {isComplete ? "Setup complete!" : "Getting started"}
              </p>
              <p className="text-xs text-muted-foreground">
                {isComplete
                  ? "You're ready to go"
                  : `${completedCount} of ${totalCount} complete`}
              </p>
            </div>
            {isExpanded ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronUp className="h-4 w-4 text-muted-foreground" />
            )}
          </button>

          {/* Expanded content */}
          <AnimatePresence>
            {isExpanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
              >
                <div className="border-t border-border">
                  {/* Progress bar */}
                  <div className="px-4 pt-3 pb-2">
                    <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
                      <motion.div
                        className="h-full bg-gradient-to-r from-emerald-500 to-blue-500"
                        initial={{ width: 0 }}
                        animate={{ width: `${progress}%` }}
                        transition={{ duration: 0.5, ease: "easeOut" }}
                      />
                    </div>
                  </div>

                  {/* Checklist items */}
                  <div className="px-2 pb-2 max-h-64 overflow-y-auto">
                    {items.map((item, index) => {
                      const Icon = item.icon
                      return (
                        <motion.div
                          key={item.id}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: index * 0.05 }}
                        >
                          <Link
                            href={item.href}
                            onClick={() => !item.completed && markComplete(item.id)}
                            className={cn(
                              "flex items-center gap-3 p-3 rounded-xl transition-colors",
                              item.completed
                                ? "opacity-60"
                                : "hover:bg-secondary/50"
                            )}
                          >
                            <div
                              className={cn(
                                "h-8 w-8 rounded-lg flex items-center justify-center shrink-0 transition-colors",
                                item.completed
                                  ? "bg-emerald-500/10"
                                  : "bg-secondary"
                              )}
                            >
                              {item.completed ? (
                                <Check className="h-4 w-4 text-emerald-500" />
                              ) : (
                                <Icon className="h-4 w-4 text-muted-foreground" />
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p
                                className={cn(
                                  "text-sm font-medium truncate",
                                  item.completed
                                    ? "text-muted-foreground line-through"
                                    : "text-foreground"
                                )}
                              >
                                {item.title}
                              </p>
                              <p className="text-xs text-muted-foreground truncate">
                                {item.description}
                              </p>
                            </div>
                            {!item.completed && (
                              <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0" />
                            )}
                          </Link>
                        </motion.div>
                      )
                    })}
                  </div>

                  {/* Footer */}
                  <div className="px-4 py-3 border-t border-border bg-secondary/30">
                    {isComplete ? (
                      <Button
                        onClick={dismiss}
                        className="w-full bg-emerald-500 hover:bg-emerald-600"
                      >
                        <Sparkles className="h-4 w-4 mr-2" />
                        Dismiss checklist
                      </Button>
                    ) : (
                      <button
                        onClick={dismiss}
                        className="w-full text-center text-xs text-muted-foreground hover:text-foreground transition-colors"
                      >
                        Skip for now
                      </button>
                    )}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </AnimatePresence>
  )
}

// Inline progress card (for dashboard)
export function OnboardingProgressCard({ className }: { className?: string }) {
  const { items, completedCount, totalCount, progress, isComplete, isDismissed, dismiss } =
    useOnboarding()

  if (isDismissed || isComplete) {
    return null
  }

  const nextItem = items.find((item) => !item.completed)

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "rounded-2xl border border-border bg-card p-5 relative overflow-hidden",
        className
      )}
    >
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-blue-500/5" />

      <div className="relative">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-emerald-500/20 to-blue-500/20 flex items-center justify-center">
              <Rocket className="h-5 w-5 text-emerald-500" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Getting started</h3>
              <p className="text-xs text-muted-foreground">
                {completedCount} of {totalCount} steps complete
              </p>
            </div>
          </div>
          <button
            onClick={dismiss}
            className="h-8 w-8 rounded-lg hover:bg-secondary flex items-center justify-center transition-colors"
          >
            <X className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>

        {/* Progress bar */}
        <div className="h-2 rounded-full bg-secondary overflow-hidden mb-4">
          <motion.div
            className="h-full bg-gradient-to-r from-emerald-500 to-blue-500"
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.5, ease: "easeOut" }}
          />
        </div>

        {/* Next step */}
        {nextItem && (
          <Link
            href={nextItem.href}
            className="flex items-center gap-3 p-3 rounded-xl bg-secondary/50 hover:bg-secondary transition-colors group"
          >
            <div className="h-8 w-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
              <nextItem.icon className="h-4 w-4 text-emerald-500" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-foreground">
                Next: {nextItem.title}
              </p>
              <p className="text-xs text-muted-foreground">{nextItem.description}</p>
            </div>
            <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:translate-x-1 transition-transform" />
          </Link>
        )}
      </div>
    </motion.div>
  )
}
