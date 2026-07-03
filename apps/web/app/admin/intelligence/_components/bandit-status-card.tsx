"use client"

import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { intelligenceApi } from "@/lib/api"
import { NotYetPopulated, SectionCard } from "./shared"

type StrategyRow = {
  strategy_key?: string
  win?: number
  loss?: number
  win_rate?: number
  ucb_score?: number
}

type ClusterSegmentRow = {
  cluster_id?: string
  segment_prefix?: string
  decided_samples?: number
  top_strategy_key?: string
  ucb_score?: number
}

export function BanditStatusCard({ enabled }: { enabled: boolean }) {
  const { data, isLoading, error } = useSWR(enabled ? "admin/intelligence/bandit-status" : null, () =>
    intelligenceApi.banditStatus(),
  )
  if (!enabled) return null
  if (isLoading) {
    return (
      <SectionCard title="Strategy bandit v3" description="Loading ledger stats…">
        <p className="text-sm text-muted-foreground">Fetching strategy performance records…</p>
      </SectionCard>
    )
  }
  if (error) {
    return (
      <SectionCard title="Strategy bandit v3" description="Unable to load bandit status.">
        <p className="text-sm text-muted-foreground">Try refreshing the page.</p>
      </SectionCard>
    )
  }
  const summary = (data?.summary as Record<string, unknown>) || {}
  const recordCount = Number(summary.record_count ?? summary.recordCount ?? 0)
  const top = (summary.top_strategies as StrategyRow[]) || []
  const clusterSegments = (summary.cluster_segments as ClusterSegmentRow[]) || []
  const scopeNote = String(data?.scope_note || data?.scopeNote || "")
  const phaseStatus = String(data?.phase_e_status || "complete")
  return (
    <SectionCard
      title="Strategy bandit v3"
      description="Cluster-segment UCB with v2 fallback — active policy layer."
      action={
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="font-normal">
            {String(data?.active_bandit_version || data?.bandit_version || summary.bandit_version || "v3")}
          </Badge>
          <Badge variant="secondary" className="font-normal capitalize">
            {phaseStatus}
          </Badge>
        </div>
      }
    >
      {recordCount === 0 ? (
        <NotYetPopulated>No strategy performance records yet. Outcomes will populate the ledger.</NotYetPopulated>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">{scopeNote}</p>
          <div className="overflow-x-auto rounded-xl border border-border/60">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-border/60 text-left text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Strategy</th>
                  <th className="px-3 py-2 font-medium">Wins</th>
                  <th className="px-3 py-2 font-medium">Losses</th>
                  <th className="px-3 py-2 font-medium">Win rate</th>
                  <th className="px-3 py-2 font-medium">UCB</th>
                </tr>
              </thead>
              <tbody>
                {top.slice(0, 6).map((row) => (
                  <tr key={row.strategy_key} className="border-b border-border/40 last:border-0">
                    <td className="px-3 py-2 font-mono text-xs">{row.strategy_key}</td>
                    <td className="px-3 py-2 tabular-nums">{row.win ?? 0}</td>
                    <td className="px-3 py-2 tabular-nums">{row.loss ?? 0}</td>
                    <td className="px-3 py-2 tabular-nums">
                      {row.win_rate != null ? `${Math.round(row.win_rate * 100)}%` : "—"}
                    </td>
                    <td className="px-3 py-2 tabular-nums">
                      {row.ucb_score != null ? row.ucb_score.toFixed(2) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {clusterSegments.length > 0 ? (
            <div className="overflow-x-auto rounded-xl border border-border/60">
              <p className="border-b border-border/60 px-3 py-2 text-xs font-medium text-muted-foreground">
                Cluster segments (v3 UCB)
              </p>
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-border/60 text-left text-muted-foreground">
                    <th className="px-3 py-2 font-medium">Cluster</th>
                    <th className="px-3 py-2 font-medium">Top strategy</th>
                    <th className="px-3 py-2 font-medium">Samples</th>
                    <th className="px-3 py-2 font-medium">UCB</th>
                  </tr>
                </thead>
                <tbody>
                  {clusterSegments.slice(0, 5).map((row) => (
                    <tr key={row.cluster_id} className="border-b border-border/40 last:border-0">
                      <td className="px-3 py-2 font-mono text-xs">{row.cluster_id?.slice(0, 8) ?? "—"}</td>
                      <td className="px-3 py-2 font-mono text-xs">{row.top_strategy_key ?? "—"}</td>
                      <td className="px-3 py-2 tabular-nums">{row.decided_samples ?? 0}</td>
                      <td className="px-3 py-2 tabular-nums">
                        {row.ucb_score != null ? row.ucb_score.toFixed(2) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      )}
    </SectionCard>
  )
}
