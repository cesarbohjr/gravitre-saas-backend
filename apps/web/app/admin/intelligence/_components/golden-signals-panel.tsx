"use client"

import useSWR from "swr"
import { StatCard, StatsGrid } from "@/components/gravitre/page-header"
import { intelligenceApi } from "@/lib/api"
import { cn } from "@/lib/utils"

type GoldenSignalsResponse = {
  period: string
  generated_at: string
  deploy_smoke?: {
    pass?: boolean
    verdict?: string
    created_at?: string
    git_sha?: string
  } | null
  hardening_smoke?: {
    pass?: boolean
    verdict?: string
    created_at?: string
  } | null
  fallthrough?: {
    fallthrough_pct?: number
    live_completed?: number
    live_fallthrough?: number
    alerts?: string[]
    alert_threshold_pct?: number
  }
  prefix_cache?: {
    avg_cached_prompt_ratio?: number | null
    avg_ttft_delta_ms?: number | null
  }
  r2_removal_gates?: {
    ready?: boolean
    current_fallthrough_pct?: number
  }
}

export function GoldenSignalsPanel({ className }: { className?: string }) {
  const { data, error, isLoading } = useSWR(
    ["admin-golden-signals"],
    () => intelligenceApi.goldenSignals(),
    { revalidateOnFocus: false, refreshInterval: 60_000 },
  )
  const signals = data as GoldenSignalsResponse | undefined
  const deploy = signals?.deploy_smoke
  const hardening = signals?.hardening_smoke
  const ft = signals?.fallthrough
  const cache = signals?.prefix_cache

  return (
    <section
      data-testid="golden-signals-panel"
      className={cn("rounded-lg border border-border/60 bg-card/40 p-4", className)}
      aria-label="Platform golden signals"
    >
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium tracking-tight">Golden signals</h3>
        <span className="text-xs text-muted-foreground">
          {isLoading ? "Loading…" : error ? "Unavailable" : signals?.period ?? "24h"}
        </span>
      </div>
      <StatsGrid columns={3}>
        <StatCard
          label="Deploy smoke"
          value={
            deploy?.pass === true
              ? "PASS"
              : deploy?.pass === false
                ? "FAIL"
                : deploy?.verdict?.slice(0, 12) ?? "—"
          }
          variant={deploy?.pass === true ? "success" : deploy?.pass === false ? "danger" : "default"}
        />
        <StatCard
          label="LIVE fallthrough (24h)"
          value={ft?.fallthrough_pct != null ? `${ft.fallthrough_pct}%` : "—"}
          variant={ft?.alerts?.length ? "warning" : "default"}
        />
        <StatCard
          label="Nightly hardening"
          value={
            hardening?.pass === true
              ? "PASS"
              : hardening?.pass === false
                ? "FAIL"
                : "—"
          }
          variant={hardening?.pass === true ? "success" : hardening?.pass === false ? "danger" : "default"}
        />
        <StatCard
          label="Prefix cache ratio"
          value={
            cache?.avg_cached_prompt_ratio != null
              ? `${Math.round(cache.avg_cached_prompt_ratio * 100)}%`
              : "—"
          }
        />
        <StatCard
          label="TTFT cache delta"
          value={cache?.avg_ttft_delta_ms != null ? `${cache.avg_ttft_delta_ms}ms` : "—"}
        />
        <StatCard
          label="R2 removal ready"
          value={signals?.r2_removal_gates?.ready ? "Yes" : "No"}
          variant={signals?.r2_removal_gates?.ready ? "success" : "default"}
        />
      </StatsGrid>
    </section>
  )
}
