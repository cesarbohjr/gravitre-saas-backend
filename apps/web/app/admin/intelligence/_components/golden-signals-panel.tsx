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
  research_lookups?: {
    configured_provider?: string
    sample_count?: number
    serper_pct?: number
    fallback_pct?: number
    by_provider?: Record<string, number>
    alerts?: string[]
  }
  r2_removal_gates?: {
    ready?: boolean
    current_fallthrough_pct?: number
  }
}

function passFail(pass: boolean | undefined, empty = "—"): string {
  if (pass === true) return "Healthy"
  if (pass === false) return "Needs attention"
  return empty
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
  const research = signals?.research_lookups

  return (
    <section
      data-testid="golden-signals-panel"
      className={cn("rounded-2xl border border-border/60 bg-card/40 p-4 sm:p-5", className)}
      aria-label="Platform health"
    >
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 className="text-sm font-medium tracking-tight">Platform health</h3>
          <p className="mt-0.5 text-xs text-muted-foreground text-pretty">
            Speed, reliability, and deploy checks for Gravitre in your org.
          </p>
        </div>
        <span className="text-xs text-muted-foreground">
          {isLoading ? "Loading…" : error ? "Unavailable" : `Last ${signals?.period ?? "24h"}`}
        </span>
      </div>
      <StatsGrid columns={3}>
        <StatCard
          label="Latest deploy check"
          value={
            deploy?.pass != null
              ? passFail(deploy.pass)
              : deploy?.verdict?.replace(/_/g, " ").slice(0, 18) ?? "—"
          }
          variant={deploy?.pass === true ? "success" : deploy?.pass === false ? "danger" : "default"}
        />
        <StatCard
          label="Ungoverned fallback rate"
          value={ft?.fallthrough_pct != null ? `${ft.fallthrough_pct}%` : "—"}
          variant={ft?.alerts?.length ? "warning" : "default"}
        />
        <StatCard
          label="Nightly reliability check"
          value={passFail(hardening?.pass)}
          variant={hardening?.pass === true ? "success" : hardening?.pass === false ? "danger" : "default"}
        />
        <StatCard
          label="Time to first token (typical)"
          value={ttft?.wall_p50_ms != null ? `${ttft.wall_p50_ms} ms` : "—"}
          variant={ttft?.alerts?.length ? "warning" : "default"}
        />
        <StatCard
          label="Time to first token (slow / max)"
          value={
            ttft?.wall_p99_ms != null || ttft?.wall_max_ms != null
              ? `${ttft?.wall_p99_ms ?? "—"} / ${ttft?.wall_max_ms ?? "—"} ms`
              : "—"
          }
          variant={ttft?.alerts?.length ? "warning" : "default"}
        />
        <StatCard
          label="AI page ready time (typical)"
          value={
            mount?.ai_nav_to_interactive_p50_ms != null
              ? `${mount.ai_nav_to_interactive_p50_ms} ms`
              : "—"
          }
          variant={mount?.alerts?.length ? "warning" : "default"}
        />
        <StatCard
          label="Prompt reuse (cache)"
          value={
            cache?.avg_cached_prompt_ratio != null
              ? `${Math.round(cache.avg_cached_prompt_ratio * 100)}%`
              : "—"
          }
        />
        <StatCard
          label="Cache speed gain"
          value={cache?.avg_ttft_delta_ms != null ? `${cache.avg_ttft_delta_ms} ms` : "—"}
        />
        <StatCard
          label="Research lookups healthy"
          value={
            research?.sample_count
              ? `${research.serper_pct ?? 0}% primary (${research.sample_count})`
              : "—"
          }
          variant={research?.alerts?.length ? "warning" : "default"}
        />
      </StatsGrid>
    </section>
  )
}
