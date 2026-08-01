"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { Brain } from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { BuiltInModelsBrain } from "@/components/gravitre/built-in-models-brain"
import { PageHeader } from "@/components/gravitre/page-header"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"
import { intelligenceApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { readNumber, readString } from "@/lib/intelligence/helpers"
import { SURFACE_COPY } from "@/lib/surface-copy"
import {
  getBuiltInModelGuide,
  type BuiltInModelListItem,
} from "@/lib/built-in-model-catalog"
import { cn } from "@/lib/utils"

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

const FILTERS: Array<{ id: FilterKey; label: string }> = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "needs_data", label: "Need more data" },
  { id: "roadmap", label: "Coming later" },
]

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
        <PageHeader
          title={copy.title}
          description={copy.intro}
          icon={Brain}
          iconColor="from-emerald-500/20 to-teal-500/20"
          actions={
            <div className="flex flex-wrap gap-1.5">
              {FILTERS.map((f) => (
                <Button
                  key={f.id}
                  size="sm"
                  variant={filter === f.id ? "default" : "outline"}
                  className={cn("h-8 text-xs", filter === f.id && "shadow-sm")}
                  onClick={() => setFilter(f.id)}
                >
                  {f.label}
                </Button>
              ))}
            </div>
          }
        />

        <div className="px-4 pb-8 md:px-6">
          {isLoading && !data ? (
            <p className="text-sm text-muted-foreground">Loading your org ML brain…</p>
          ) : items.length === 0 ? (
            <EmptyState title={copy.emptyTitle} description={copy.emptyDescription} />
          ) : (
            <BuiltInModelsBrain items={items} filter={filter} />
          )}
        </div>
      </div>
    </AppShell>
  )
}
