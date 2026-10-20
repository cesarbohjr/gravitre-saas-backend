"use client"

import useSWR from "swr"
import { HardDrive } from "lucide-react"
import { cn } from "@/lib/utils"
import { storageApi, type StorageCategory, type StorageUsage } from "@/lib/api"

const CATEGORY_LABELS: Record<StorageCategory, { label: string; hint: string; bar: string }> = {
  knowledge: { label: "Knowledge", hint: "Indexed documents, chunks and embeddings", bar: "bg-chart-1" },
  memories: { label: "Memories", hint: "Agent memories and their history", bar: "bg-chart-2" },
  conversations: { label: "Conversations", hint: "Chat threads and messages", bar: "bg-chart-3" },
  audit: { label: "Audit log", hint: "Activity and audit records", bar: "bg-chart-4" },
  files: { label: "Files", hint: "Uploaded and generated files", bar: "bg-muted-foreground" },
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null || !Number.isFinite(bytes)) return "—"
  const units = ["B", "KB", "MB", "GB", "TB"]
  let value = Math.max(0, bytes)
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  const digits = value >= 100 || unit === 0 ? 0 : 1
  return `${value.toFixed(digits)} ${units[unit]}`
}

/**
 * Storage used by this workspace vs its plan allowance, by category.
 * Renders nothing while the storage meter is switched off; shows a short
 * empty state until the first daily snapshot exists.
 */
export function StorageUsageCard({ className }: { className?: string }) {
  const { data, error } = useSWR<StorageUsage>("settings-storage-usage", () => storageApi.getUsage(), {
    revalidateOnFocus: false,
  })

  if (error || !data || !data.meterEnabled) return null

  const snapshot = data.snapshot
  const limit = data.limitBytes
  const used = snapshot?.totalBytes ?? 0
  const percent = data.percentUsed ?? (limit && limit > 0 ? (used / limit) * 100 : null)
  const tone =
    data.state === "over" ? "text-destructive" : data.state === "warn" ? "text-warning" : "text-muted-foreground"

  return (
    <section
      aria-labelledby="storage-usage-heading"
      className={cn(
        "rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] shadow-[var(--np-shadow)] p-4",
        className,
      )}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <HardDrive className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          <h3 id="storage-usage-heading" className="text-sm font-semibold text-foreground">
            Storage
          </h3>
        </div>
        {snapshot ? (
          <span className={cn("text-xs tabular-nums", tone)}>
            {percent != null ? `${Math.round(percent)}%` : "No limit"}
          </span>
        ) : null}
      </div>

      {!snapshot ? (
        <p className="text-sm text-muted-foreground">
          Storage usage is measured once a day. Your first measurement will appear here soon.
        </p>
      ) : (
        <>
          <div className="mb-3 flex items-baseline gap-1.5">
            <p className="text-2xl font-semibold tracking-tight text-foreground tabular-nums">{formatBytes(used)}</p>
            <p className="text-sm text-muted-foreground tabular-nums">
              {limit != null ? `/ ${formatBytes(limit)}` : "used"}
            </p>
          </div>

          <div
            className="flex h-1.5 overflow-hidden rounded-full bg-muted/80"
            role="img"
            aria-label={`Storage used: ${formatBytes(used)}${limit != null ? ` of ${formatBytes(limit)}` : ""}`}
          >
            {data.categories.map((category) => {
              const bytes = snapshot.categories[category]?.bytes ?? 0
              const base = limit && limit > 0 ? Math.max(limit, used) : used || 1
              const width = (bytes / base) * 100
              if (width <= 0) return null
              return (
                <div
                  key={category}
                  className={cn("h-full", data.state === "over" ? "bg-destructive" : CATEGORY_LABELS[category].bar)}
                  style={{ width: `${width}%` }}
                />
              )
            })}
          </div>

          <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
            {data.categories.map((category) => (
              <div key={category} className="flex items-center justify-between gap-3">
                <dt className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground" title={CATEGORY_LABELS[category].hint}>
                  <span className={cn("h-2 w-2 shrink-0 rounded-full", CATEGORY_LABELS[category].bar)} aria-hidden="true" />
                  <span className="truncate">{CATEGORY_LABELS[category].label}</span>
                </dt>
                <dd className="text-xs font-medium tabular-nums text-foreground">
                  {formatBytes(snapshot.categories[category]?.bytes ?? 0)}
                </dd>
              </div>
            ))}
          </dl>

          {data.state === "warn" ? (
            <p className="mt-3 text-[11px] font-medium text-warning">
              You have used most of your storage allowance.
              {data.enforcementEnabled ? " New syncs and uploads pause when it is full." : ""}
            </p>
          ) : null}
          {data.state === "over" ? (
            <p className="mt-3 text-[11px] font-medium text-destructive">
              {data.enforcementEnabled
                ? "Storage allowance reached. New syncs and uploads are paused; nothing has been deleted."
                : "Storage allowance reached."}
            </p>
          ) : null}
          <p className="mt-2 text-[11px] leading-snug text-muted-foreground">
            Measured {new Date(snapshot.capturedAt).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
            . Sizes are estimates and include search indexes.
          </p>
        </>
      )}
    </section>
  )
}
