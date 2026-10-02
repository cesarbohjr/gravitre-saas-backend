"use client"

import { Badge } from "@/components/ui/badge"
import { CheckCircle2, Gauge, ShieldCheck, Workflow } from "lucide-react"

type JsonObject = Record<string, unknown>

function object(value: unknown): JsonObject | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonObject) : null
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && Boolean(item.trim())) : []
}

function rows(value: unknown): JsonObject[] {
  return Array.isArray(value) ? value.map(object).filter((item): item is JsonObject => Boolean(item)) : []
}

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null
}

function verificationLabel(config: JsonObject): string {
  const profiles = rows(config.runtime_profiles)
  if (profiles.some((profile) => profile.status === "production_verified")) return "Production Verified"
  if (profiles.length) return "Runtime profiled"
  return "Governed"
}

export function OutcomePackOverview({ config }: { config?: Record<string, unknown> | null }) {
  if (!config) return null
  const outcome = object(config.outcome_contract)
  const plays = rows(config.plays)
  const dashboard = object(config.dashboard)
  const kpis = rows(outcome?.kpis)
  const criteria = strings(outcome?.success_criteria)
  const profiles = rows(config.runtime_profiles)
  const isOutcomePack = config.marketplace_version === "3.0" && Boolean(outcome)
  if (!isOutcomePack) return null

  const target = text(outcome?.target_outcome)
  const problem = text(outcome?.problem)
  const dashboardTitle = text(dashboard?.title)
  const verifiedProviders = profiles
    .filter((profile) => profile.status === "production_verified")
    .map((profile) => text(profile.provider))
    .filter((provider): provider is string => Boolean(provider))

  return (
    <section className="space-y-4" data-testid="marketplace3-outcome-overview">
      <div className="rounded-xl border border-primary/20 bg-primary/[0.04] p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">Marketplace 3.0</Badge>
          <Badge className="gap-1 bg-success/10 text-success hover:bg-success/10">
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
            {verificationLabel(config)}
          </Badge>
          {verifiedProviders.map((provider) => (
            <Badge key={provider} variant="secondary" className="capitalize">
              {provider}
            </Badge>
          ))}
        </div>
        {target ? <h2 className="mt-3 text-lg font-semibold tracking-tight text-foreground">{target}</h2> : null}
        {problem ? <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{problem}</p> : null}
      </div>

      {plays.length ? (
        <div className="rounded-xl border bg-card p-4">
          <div className="flex items-center gap-2">
            <Workflow className="h-4 w-4 text-primary" aria-hidden />
            <h2 className="text-sm font-semibold text-foreground">{plays.length} outcome-driven Plays</h2>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {plays.map((play, index) => {
              const name = text(play.name) ?? text(play.key) ?? `Play ${index + 1}`
              const description = text(play.description)
              return (
                <div key={text(play.key) ?? `${name}-${index}`} className="rounded-lg border bg-muted/15 p-3">
                  <p className="text-sm font-medium text-foreground">{name}</p>
                  {description ? <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{description}</p> : null}
                </div>
              )
            })}
          </div>
        </div>
      ) : null}

      {kpis.length ? (
        <div className="rounded-xl border bg-card p-4">
          <div className="flex items-center gap-2">
            <Gauge className="h-4 w-4 text-primary" aria-hidden />
            <h2 className="text-sm font-semibold text-foreground">{dashboardTitle ?? "Measured outcomes"}</h2>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {kpis.map((kpi, index) => {
              const label = text(kpi.label) ?? text(kpi.key) ?? `KPI ${index + 1}`
              const unit = text(kpi.unit)
              const direction = text(kpi.direction)
              return (
                <div key={text(kpi.key) ?? `${label}-${index}`} className="rounded-lg bg-muted/25 px-3 py-2.5">
                  <p className="text-xs font-medium text-foreground">{label}</p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">
                    {[unit, direction ? `target: ${direction}` : null].filter(Boolean).join(" · ")}
                  </p>
                </div>
              )
            })}
          </div>
        </div>
      ) : null}

      {criteria.length ? (
        <div className="rounded-xl border bg-card p-4">
          <h2 className="text-sm font-semibold text-foreground">Verification contract</h2>
          <ul className="mt-3 space-y-2">
            {criteria.map((criterion) => (
              <li key={criterion} className="flex items-start gap-2 text-sm text-muted-foreground">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden />
                <span>{criterion}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}
