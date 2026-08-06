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
  ttft?: {
    wall_p50_ms?: number | null
    wall_p99_ms?: number | null
    wall_max_ms?: number | null
    sample_count?: number
    alerts?: string[]
  }
  mount_tti?: {
    ai_nav_to_interactive_p50_ms?: number | null
    ai_nav_to_interactive_max_ms?: number | null
    sample_count?: number
    alerts?: string[]
  }
  alerts?: string[]
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
  const ttft = signals?.ttft
  const mount = signals?.mount_tti

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
          label="TTFT wall p50"
          value={ttft?.wall_p50_ms != null ? `${ttft.wall_p50_ms}ms` : "—"}
          variant={ttft?.alerts?.length ? "warning" : "default"}
        />
        <StatCard
          label="TTFT wall p99 / max"
          value={
            ttft?.wall_p99_ms != null || ttft?.wall_max_ms != null
              ? `${ttft?.wall_p99_ms ?? "—"} / ${ttft?.wall_max_ms ?? "—"}ms`
              : "—"
          }
          variant={ttft?.alerts?.length ? "warning" : "default"}
        />
        <StatCard
          label="Mount /ai nav→TTI p50"
          value={
            mount?.ai_nav_to_interactive_p50_ms != null
              ? `${mount.ai_nav_to_interactive_p50_ms}ms`
              : "—"
          }
          variant={mount?.alerts?.length ? "warning" : "default"}
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
