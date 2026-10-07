"use client"

import { motion, useReducedMotion } from "framer-motion"
import {
  IntelligenceHubTabs,
  type IntelligenceHubTab,
} from "@/components/intelligence/intelligence-hub-tabs"
import { IntelligenceFreshnessBar } from "@/components/intelligence/shell/intelligence-freshness-bar"
import type { SnapshotLoadState } from "@/lib/intelligence/snapshot-state"
import { cn } from "@/lib/utils"
import type { ReactNode } from "react"

/**
 * I1 — permanent Intelligence Experience Shell.
 * All hub routes inherit: single nav, freshness, optional filters/command slots, page frame.
 */
export function IntelligenceShell({
  activeTab,
  children,
  filters,
  commandBar,
  loadState = "UNINITIALIZED",
  generatedAt,
  isValidating,
  onRefresh,
  className,
  bodyClassName,
  chrome = "full",
  showFreshness = false,
}: {
  activeTab?: IntelligenceHubTab
  children: ReactNode
  filters?: ReactNode
  commandBar?: ReactNode
  loadState?: SnapshotLoadState
  generatedAt?: string | null
  isValidating?: boolean
  onRefresh?: () => void
  className?: string
  bodyClassName?: string
  /** "none" when the page header already carries hub tabs and freshness. */
  chrome?: "full" | "none"
  /** Show the snapshot freshness line in the tab row. Off by default: the v2 designs put "Updated" in the page header where they show it at all. */
  showFreshness?: boolean
}) {
  const reduceMotion = useReducedMotion()

  return (
    <div className={cn("space-y-4", className)}>
      {chrome === "full" ? (
        <div className="flex flex-col gap-2 border-b border-[color:var(--g-border-subtle)] sm:flex-row sm:items-end sm:justify-between">
          <IntelligenceHubTabs active={activeTab} />
          <div className="flex flex-wrap items-center gap-2 pb-2">
            {showFreshness ? (
              <IntelligenceFreshnessBar
                loadState={loadState}
                generatedAt={generatedAt}
                isValidating={isValidating}
                onRefresh={onRefresh}
              />
            ) : null}
            {filters}
          </div>
        </div>
      ) : filters ? (
        <div className="flex flex-wrap items-center gap-2">{filters}</div>
      ) : null}

      {commandBar}

      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: reduceMotion ? 0 : 0.22, ease: "easeOut" }}
        className={bodyClassName}
      >
        {children}
      </motion.div>
    </div>
  )
}
