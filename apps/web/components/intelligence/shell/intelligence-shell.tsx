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
}) {
  const reduceMotion = useReducedMotion()

  return (
    <div className={cn("space-y-4", className)}>
      <IntelligenceHubTabs active={activeTab} className="flex-wrap" />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <IntelligenceFreshnessBar
          loadState={loadState}
          generatedAt={generatedAt}
          isValidating={isValidating}
          onRefresh={onRefresh}
        />
        {filters ? <div className="flex flex-wrap items-center gap-2">{filters}</div> : null}
      </div>

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
