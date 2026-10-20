"use client"

import useSWR from "swr"
import { CheckCircle2, Circle, Clock, FileSearch } from "lucide-react"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { connectorVendorKey } from "@/lib/connectors"
import { cn } from "@/lib/utils"
import { TYPE } from "@/lib/design-system"

export const DATA_REMOVAL_KEY = "/api/connectors/data-removal"

export type DataRemovalPolicy = {
  /** off: nothing is removed yet; test: a receipt lists what would be removed; on: removed. */
  dataRemoval: "off" | "test" | "on"
  memoriesIncluded: boolean
  providerRevokeEnabled: boolean
  providerRevokeVendors: string[]
  deletionPropagationEnabled: boolean
}

export type DataRemovalEntry = {
  connectorId: string
  name: string
  vendor: string
  disconnectedAt: string | null
  status: "removed" | "planned" | "queued" | "not_started"
  receiptAt: string | null
  counts: Record<string, unknown>
}

export type DataRemovalResponse = {
  policy: DataRemovalPolicy
  removals: DataRemovalEntry[]
}

export function useDataRemoval(enabled = true) {
  return useSWR<DataRemovalResponse>(enabled ? DATA_REMOVAL_KEY : null, apiFetcher, {
    revalidateOnFocus: false,
  })
}

function supportsRevoke(policy: DataRemovalPolicy, vendor: string): boolean {
  const key = connectorVendorKey(vendor)
  return policy.providerRevokeVendors.some((v) => connectorVendorKey(v) === key)
}

/** What disconnecting this connector does, worded from the switches that actually run. */
export function disconnectImpactLines(
  policy: DataRemovalPolicy | undefined,
  vendorLabel: string,
  vendor: string,
): string[] {
  const lines = ["Gravitre stops syncing and deletes the sign-in tokens it stored for this connection."]
  if (!policy) {
    lines.push("Indexed content and anything learned from this source may be kept until removal runs.")
    return lines
  }
  if (policy.memoriesIncluded) {
    lines.push("Agents stop using memories and customer insights learned from this source right away.")
  }
  const derived = policy.memoriesIncluded
    ? "indexed documents, extracted records, memories and customer insights"
    : "indexed documents and extracted records"
  if (policy.dataRemoval === "on") {
    lines.push(`The ${derived} from this source are permanently deleted. A removal receipt appears on the Connectors page.`)
  } else if (policy.dataRemoval === "test") {
    lines.push(
      `Data removal is in test mode: the ${derived} are kept, and a receipt on the Connectors page lists what would be deleted.`,
    )
  } else {
    lines.push(`Automatic data removal is not switched on yet, so the ${derived} are kept for now.`)
  }
  if (policy.providerRevokeEnabled && supportsRevoke(policy, vendor)) {
    lines.push(`Gravitre asks ${vendorLabel} to revoke its access. To reconnect later you sign in again.`)
  } else {
    lines.push(`Gravitre's access is not revoked inside ${vendorLabel}. You can remove the app from ${vendorLabel}'s settings.`)
  }
  return lines
}

export function DisconnectImpact({
  policy,
  vendorLabel,
  vendor,
  className,
}: {
  policy: DataRemovalPolicy | undefined
  vendorLabel: string
  vendor: string
  className?: string
}) {
  return (
    <ul className={cn("space-y-1.5 text-sm text-muted-foreground", className)} data-testid="disconnect-impact">
      {disconnectImpactLines(policy, vendorLabel, vendor).map((line) => (
        <li key={line} className="flex gap-2">
          <span aria-hidden className="mt-2 h-1 w-1 shrink-0 rounded-full bg-muted-foreground" />
          <span>{line}</span>
        </li>
      ))}
    </ul>
  )
}

const COUNT_LABELS: Array<[string, string]> = [
  ["rag_documents", "documents"],
  ["rag_chunks", "indexed passages"],
  ["entities", "records"],
  ["agent_memories", "memories"],
  ["entity_observations", "customer insights"],
]

function countSummary(counts: Record<string, unknown>): string {
  const parts = COUNT_LABELS.flatMap(([key, label]) => {
    const n = counts[key]
    return typeof n === "number" ? [`${n.toLocaleString()} ${label}`] : []
  })
  return parts.join(", ")
}

const STATUS_COPY: Record<DataRemovalEntry["status"], { label: string; icon: typeof Circle; tone: string }> = {
  removed: { label: "Removed", icon: CheckCircle2, tone: "text-success" },
  planned: { label: "Test run, nothing deleted", icon: FileSearch, tone: "text-muted-foreground" },
  queued: { label: "Removal queued", icon: Clock, tone: "text-muted-foreground" },
  not_started: { label: "Data kept, removal not switched on", icon: Circle, tone: "text-muted-foreground" },
}

function formatWhen(iso: string | null): string {
  if (!iso) return ""
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}

/** Recent disconnects and what was removed (or would be, in test mode). Renders nothing when there are none. */
export function DataRemovalReceipts({ className }: { className?: string }) {
  const { data } = useDataRemoval()
  const removals = data?.removals ?? []
  if (removals.length === 0) return null
  return (
    <section aria-labelledby="data-removal-heading" className={cn("min-w-0", className)} data-testid="data-removal-receipts">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <h2 id="data-removal-heading" className="text-[13px] font-semibold text-foreground">
          Removed connections
        </h2>
        <p className={TYPE.meta}>Last 90 days</p>
      </div>
      <ul className="divide-y divide-[color:var(--g-border-default)] rounded-lg border border-[color:var(--g-border-default)]">
        {removals.map((r) => {
          const status = STATUS_COPY[r.status] ?? STATUS_COPY.queued
          const Icon = status.icon
          const summary = r.status === "removed" || r.status === "planned" ? countSummary(r.counts) : ""
          return (
            <li key={`${r.connectorId}-${r.disconnectedAt}`} className="flex items-start gap-3 px-3 py-2.5">
              <ConnectorIcon vendor={r.vendor} size="sm" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <p className="truncate text-sm font-medium text-foreground">{r.name}</p>
                  <p className={TYPE.meta}>Disconnected {formatWhen(r.disconnectedAt)}</p>
                </div>
                <p className={cn("mt-0.5 flex items-center gap-1.5 text-xs", status.tone)}>
                  <Icon className="h-3.5 w-3.5" aria-hidden />
                  {status.label}
                  {summary ? (
                    <span className="text-muted-foreground">
                      {" · "}
                      {r.status === "planned" ? "would delete " : ""}
                      {summary}
                    </span>
                  ) : null}
                </p>
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
