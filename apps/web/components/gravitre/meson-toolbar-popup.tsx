"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { usePathname, useRouter } from "next/navigation"
import { AnimatePresence, motion } from "framer-motion"
import { Blocks, ChevronDown, ChevronUp, X } from "lucide-react"
import { MesonPagePanel } from "@/components/gravitre/meson-page-panel"
import type { MesonSuggestion } from "@/lib/api"
import {
  resolveMesonPageFromPath,
  routeMesonSuggestion,
  shouldShowMesonToolbar,
} from "@/lib/meson-page-context"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

const HIDDEN_KEY = "gravitre-meson-toolbar-dismissed"
const COLLAPSED_KEY = "gravitre-meson-toolbar-collapsed"

function readFlag(key: string): boolean {
  if (typeof window === "undefined") return false
  return localStorage.getItem(key) === "true"
}

function writeFlag(key: string, value: boolean): void {
  if (typeof window === "undefined") return
  if (value) localStorage.setItem(key, "true")
  else localStorage.removeItem(key)
}

export function MesonToolbarPopup() {
  const pathname = usePathname()
  const router = useRouter()
  const [dismissed, setDismissed] = useState(false)
  const [collapsed, setCollapsed] = useState(true)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    setDismissed(readFlag(HIDDEN_KEY))
    setCollapsed(true)
  }, [])

  useEffect(() => {
    setCollapsed(true)
  }, [pathname])

  const visible = mounted && shouldShowMesonToolbar(pathname) && !dismissed
  const mesonPage = useMemo(() => resolveMesonPageFromPath(pathname), [pathname])

  const handleSuggestionClick = useCallback(
    (suggestion: MesonSuggestion) => {
      routeMesonSuggestion(pathname, suggestion, (href) => router.push(href))
    },
    [pathname, router],
  )

  const handleDismiss = () => {
    setDismissed(true)
    writeFlag(HIDDEN_KEY, true)
  }

  const handleToggleCollapsed = () => {
    setCollapsed((current) => {
      const next = !current
      writeFlag(COLLAPSED_KEY, next)
      return next
    })
  }

  if (!visible) return null

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-40 flex justify-center px-4 pb-4 md:justify-end md:pr-6">
      <div className="pointer-events-auto w-full max-w-md">
        <AnimatePresence initial={false}>
          {!collapsed ? (
            <motion.div
              key="meson-panel"
              initial={{ opacity: 0, y: 16, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 12, scale: 0.98 }}
              transition={{ duration: 0.2 }}
              className="mb-2 overflow-hidden rounded-2xl border border-violet-500/20 bg-card/95 shadow-xl shadow-violet-500/10 backdrop-blur-md"
            >
              <div className="flex items-center justify-between border-b border-border/60 px-3 py-2">
                <div className="flex items-center gap-2 text-xs font-medium text-foreground">
                  <Blocks className="h-3.5 w-3.5 text-violet-500" />
                  Meson tips
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    aria-label="Minimize Meson"
                    onClick={handleToggleCollapsed}
                  >
                    <ChevronDown className="h-4 w-4" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-muted-foreground hover:text-foreground"
                    aria-label="Hide Meson"
                    onClick={handleDismiss}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <div className="max-h-[min(40vh,320px)] overflow-y-auto p-3">
                <MesonPagePanel
                  page={mesonPage.page}
                  entityId={mesonPage.entityId}
                  compact
                  onSuggestionClick={handleSuggestionClick}
                />
              </div>
            </motion.div>
          ) : null}
        </AnimatePresence>

        <button
          type="button"
          onClick={handleToggleCollapsed}
          className={cn(
            "flex w-full items-center justify-between gap-3 rounded-full border px-4 py-2.5 text-sm shadow-lg backdrop-blur-md transition-colors",
            "border-violet-500/25 bg-card/95 hover:border-violet-500/40 hover:bg-violet-500/5",
          )}
          aria-expanded={!collapsed}
          aria-label={collapsed ? "Open Meson tips" : "Minimize Meson tips"}
        >
          <span className="flex items-center gap-2 font-medium text-foreground">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-purple-600">
              <Blocks className="h-3.5 w-3.5 text-white" />
            </span>
            Meson
          </span>
          <span className="flex items-center gap-2 text-xs text-muted-foreground">
            Tips & insights
            {collapsed ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </span>
        </button>
      </div>
    </div>
  )
}
