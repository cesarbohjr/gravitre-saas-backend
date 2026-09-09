"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { BuiltInModelsBrain } from "@/components/gravitre/built-in-models-brain"
import { GravitreMetric, GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { useAuth } from "@/lib/auth-context"
import { intelligenceApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { readNumber, readString } from "@/lib/intelligence/helpers"
import { SURFACE_COPY } from "@/lib/surface-copy"
import {
  getBuiltInModelGuide,
  statusTone,
  type BuiltInModelListItem,
} from "@/lib/built-in-model-catalog"
import { CircleDashed, Database, Pulse, Sparkles } from "@phosphor-icons/react"

type FilterKey = "all" | "active" | "needs_data" | "roadmap"

function dataSufficiencyProgress(
  modelName: string,
  status: string,
  readiness?: Record<string, unknown>,
): BuiltInModelListItem["sufficiency"] {
  if (status.toUpperCase() === "PLANNED" || status.toUpperCase() === "DISABLED") {
    return { value: null, label: "Not trainable yet", available: 0, required: 0 }
  }
  const byModel = (readiness?.by_model as Record<string, Record<string, unknown>> | undefined) ?? {}
  const entry = byModel[modelName]
  if (!entry) return { value: null, label: "Tracking starts after first signals", available: 0, required: 0 }
  const available = readNumber(entry.signals_available, 0)
  const required = readNumber(entry.min_required, 1)
  return {
    value: Math.min(100, Math.round((available / Math.max(required, 1)) * 100)),
    label: `${available} / ${required} examples`,
    available,
    required,
  }
}

export default function IntelligenceModelsPage() {
  const { user } = useAuth()
  const copy = SURFACE_COPY.builtInModels
  const [filter, setFilter] = useState<FilterKey>("all")
  const { data, error, isLoading, mutate } = useSWR(
    user ? "intelligence/models/catalog" : null,
    () => intelligenceApi.modelCatalog(),
    { revalidateOnFocus: false },
  )
  const { data: readiness } = useSWR(user ? "intelligence/training-readiness" : null, () =>
    intelligenceApi.trainingReadiness(),
  )

  const items = useMemo(() => {
    const catalog = data?.catalog ?? {}
    const orgStatus = data?.orgTrainingStatus ?? {}
    const outcomeScores = data?.outcomeScores ?? {}
    return Object.keys(catalog)
      .sort()
      .map((name) => {
        const entry = catalog[name] as Record<string, unknown>
        const statusRow = orgStatus[name]
        const status = readString(
          statusRow?.runtime_status,
          readString(statusRow?.catalog_status, readString(entry.status, "PLANNED")),
        )
        return {
          id: name,
          status,
          useCases: Array.isArray(entry.use_cases) ? (entry.use_cases as string[]) : [],
          sufficiency: dataSufficiencyProgress(name, status, readiness),
          outcomeScore: (outcomeScores[name] as number | null | undefined) ?? null,
          lastTrained: readString(
            (readiness?.by_model as Record<string, Record<string, unknown>> | undefined)?.[name]
              ?.last_trained_at,
            "—",
          ),
          guide: getBuiltInModelGuide(name),
        } satisfies BuiltInModelListItem
      })
  }, [data, readiness])

  const metrics = useMemo(() => {
    let active = 0
    let needsData = 0
    let roadmap = 0
    let withSignal = 0
    for (const row of items) {
      const tone = statusTone(row.status)
      if (tone === "ready" || tone === "learning") active += 1
      if (
        (tone === "ready" || tone === "learning") &&
        row.sufficiency.value != null &&
        row.sufficiency.value < 100
      ) {
        needsData += 1
      }
      if (tone === "planned" || tone === "off") roadmap += 1
      // Readiness API has started counting examples for this model (not a TRAINED claim).
      if (row.sufficiency.available > 0 || row.sufficiency.required > 0) {
        withSignal += 1
      }
    }
    return { active, needsData, roadmap, withSignal }
  }, [items])

  if (!user) {
    return (
      <AppShell title={copy.title}>
        <EmptyState title="Sign in required" description="Log in to view built-in models." />
      </AppShell>
    )
  }

  if (error) {
    return (
      <AppShell title={copy.title}>
        <ErrorState
          title="Unable to load built-in models"
          description={error instanceof ApiError ? error.message : "Try again in a moment."}
          onRetry={() => mutate()}
        />
      </AppShell>
    )
  }

  return (
    <AppShell title={copy.title}>
      <div className="space-y-2">
        <GravitrePageHeader
          title={copy.title}
          description={copy.intro}
          icon={<NucleoIntelligence className="h-5 w-5" />}
        />

        <div className="px-4 pb-8 md:px-6 space-y-5">
          {isLoading && !data ? (
            <p className="text-sm text-muted-foreground">Loading your org ML brain…</p>
          ) : items.length === 0 ? (
            <EmptyState title={copy.emptyTitle} description={copy.emptyDescription} />
          ) : (
            <>
              <section
                className="grid grid-cols-2 gap-[var(--np-kpi-gap)] lg:grid-cols-4"
                aria-label="Built-in model counts"
              >
                <GravitreMetric
                  label="Active"
                  value={metrics.active}
                  hint="In use (artifact or heuristic)"
                  icon={<Pulse className="h-4 w-4" weight="duotone" aria-hidden />}
                />
                <GravitreMetric
                  label="Needs data"
                  value={metrics.needsData}
                  hint="Below example threshold"
                  warning={metrics.needsData > 0}
                  icon={<Database className="h-4 w-4" weight="duotone" aria-hidden />}
                />
                <GravitreMetric
                  label="Roadmap"
                  value={metrics.roadmap}
                  hint="Planned or unavailable"
                  icon={<CircleDashed className="h-4 w-4" weight="duotone" aria-hidden />}
                />
                <GravitreMetric
                  label="With signals"
                  value={metrics.withSignal}
                  hint="Readiness tracking started"
                  icon={<Sparkles className="h-4 w-4" weight="duotone" aria-hidden />}
                />
              </section>
              <BuiltInModelsBrain items={items} filter={filter} onFilterChange={setFilter} />
            </>
          )}
        </div>
      </div>
    </AppShell>
  )
}
