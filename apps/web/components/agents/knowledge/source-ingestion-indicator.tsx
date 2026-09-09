"use client"

import { motion } from "framer-motion"
import { cn } from "@/lib/utils"

export type SourceIngestionSnapshot = {
  status?: string
  documentCount?: number
  lastSyncAt?: string | null
  syncProgress?: number | null
}

function customerStatus(status?: string): string {
  const s = (status ?? "").toLowerCase()
  if (s === "syncing" || s === "processing") return "Indexing"
  if (s === "active" || s === "connected" || s === "ready") return "Ready"
  if (s === "error" || s === "failed") return "Failed"
  if (s === "inactive" || s === "disconnected") return "Inactive"
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "Unknown"
}

export function SourceIngestionIndicator({ snapshot }: { snapshot: SourceIngestionSnapshot }) {
  const status = (snapshot.status ?? "").toLowerCase()
  const indexing = status === "syncing" || status === "processing"
  const failed = status === "error" || status === "failed"
  const ready = status === "active" || status === "connected" || status === "ready"
  const progress =
    typeof snapshot.syncProgress === "number" && snapshot.syncProgress >= 0 && snapshot.syncProgress <= 100
      ? snapshot.syncProgress
      : null

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-2 text-[10px] text-[color:var(--g-text-muted)]">
        <span
          className={cn(
            "rounded border px-1.5 py-0.5 font-medium capitalize",
            ready && "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
            indexing && "border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300",
            failed && "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300",
            !ready && !indexing && !failed && "border-border bg-secondary",
          )}
        >
          {customerStatus(snapshot.status)}
        </span>
        {snapshot.documentCount != null ? (
          <span className="tabular-nums">{snapshot.documentCount} indexed chunks</span>
        ) : null}
        {snapshot.lastSyncAt ? (
          <span>Synced {new Date(snapshot.lastSyncAt).toLocaleString()}</span>
        ) : null}
      </div>
      {indexing ? (
        <div className="space-y-1">
          {progress != null ? (
            <div className="h-1.5 overflow-hidden rounded-full bg-muted/60">
              <motion.div
                className="h-full rounded-full bg-violet-500/80"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.4 }}
              />
            </div>
          ) : (
            <div className="h-1.5 overflow-hidden rounded-full bg-muted/60">
              <motion.div
                className="h-full w-1/3 rounded-full bg-violet-500/70"
                animate={{ x: ["-100%", "300%"] }}
                transition={{ duration: 1.4, repeat: Infinity, ease: "linear" }}
              />
            </div>
          )}
          <p className="text-[10px] text-[color:var(--g-text-muted)]">Creating searchable knowledge…</p>
        </div>
      ) : null}
    </div>
  )
}
