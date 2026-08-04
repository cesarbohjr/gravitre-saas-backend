"use client"

import { useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { useParams } from "next/navigation"
import { ArrowLeft, ChartLineUp, Play } from "@phosphor-icons/react"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { StatCard, StatsGrid } from "@/components/gravitre/page-header"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAuth } from "@/lib/auth-context"
import { intelligenceApi, mlAdminApi } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { SURFACE_COPY } from "@/lib/surface-copy"
import {
  formatPercent,
  formatScore,
  modelStatusChipClass,
  plainDecisionReasoning,
  readNumber,
  readString,
} from "@/lib/intelligence/helpers"
import { getBuiltInModelGuide, statusLabel } from "@/lib/built-in-model-catalog"

export default function ModelProfilePage() {
  const { user } = useAuth()
  const params = useParams<{ name: string }>()
  const modelName = decodeURIComponent(params.name)
  const guide = getBuiltInModelGuide(modelName)
  const [training, setTraining] = useState(false)

  const { data: catalogData, error } = useSWR(user ? "intelligence/models/catalog" : null, () =>
    intelligenceApi.modelCatalog(),
  )
  const { data: readiness } = useSWR(user ? "intelligence/training-readiness" : null, () =>
    intelligenceApi.trainingReadiness(),
  )
  const { data: evaluations } = useSWR(user ? ["intelligence/evaluations", 30] : null, () =>
    intelligenceApi.intelligenceEvaluations({ periodDays: 30 }),
  )
  const { data: outcomes } = useSWR(user ? ["intelligence/outcomes", 30] : null, () =>
    intelligenceApi.outcomes({ periodDays: 30 }),
  )

  if (!user) {
    return (
      <AppShell title="Model profile">
        <EmptyState title="Sign in required" description="Log in to view this model profile." />
      </AppShell>
    )
  }

  const catalogEntry = (catalogData?.catalog?.[modelName] ?? {}) as Record<string, unknown>
  const statusEntry = catalogData?.orgTrainingStatus?.[modelName]
  if (!catalogEntry && !statusEntry && catalogData) {
    return (
      <AppShell title="Model profile">
        <EmptyState title="Model not found" description={`${modelName} is not in the org catalog.`} />
      </AppShell>
    )
  }

  if (error) {
    return (
      <AppShell title="Model profile">
        <ErrorState title="Unable to load model" description="Please try again." />
      </AppShell>
    )
  }

  // Module C / STA-331: prefer runtime_status (artifact load) over catalog TRAINED.
  const status = readString(
    statusEntry?.runtime_status,
    readString(statusEntry?.catalog_status, readString(catalogEntry.status, "PLANNED")),
  )
  const isPlanned = status.toUpperCase() === "PLANNED" || status.toUpperCase() === "DISABLED"
  const readinessEntry = ((readiness?.by_model as Record<string, Record<string, unknown>> | undefined) ?? {})[
    modelName
  ]
  const signalsAvailable = readNumber(readinessEntry?.signals_available, 0)
  const minRequired = readNumber(readinessEntry?.min_required, 1)
  const readinessStatus = readString(readinessEntry?.status, "insufficient_data")
  const progress = isPlanned ? null : Math.min(100, Math.round((signalsAvailable / Math.max(minRequired, 1)) * 100))
  const activationRequirement = readString(
    catalogEntry.min_data,
    readString(statusEntry?.activation, "See catalog requirements"),
  )

  async function handleTrain() {
    setTraining(true)
    try {
      const result = await mlAdminApi.trainModel(modelName)
      if (result.trained) toast.success(`Training queued for ${guide.label}`)
      else toast.message(result.message || result.reason || "Training not started")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Training request failed")
    } finally {
      setTraining(false)
    }
  }

  const modelPerformance = (evaluations?.model_performance as Record<string, unknown> | undefined) ?? {}
  const recentEvents = ((outcomes?.recent_events as Array<Record<string, unknown>> | undefined) ?? []).filter(
    (row) => readString(row.model_name) === modelName,
  )

  return (
    <AppShell title={guide.label}>
      <div className="space-y-6 p-4 md:p-6">
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="ghost" size="sm" asChild>
            <Link href={APP_ROUTES.builtInModels}>
              <ArrowLeft className="mr-2 h-4 w-4" aria-hidden />
              {SURFACE_COPY.builtInModels.title}
            </Link>
          </Button>
          <Badge variant="outline" className={modelStatusChipClass(status)}>
            {statusLabel(status)}
          </Badge>
          {!isPlanned && readinessStatus === "ready" ? (
            <Button size="sm" onClick={handleTrain} disabled={training}>
              <Play className="mr-2 h-4 w-4" weight="fill" aria-hidden />
              {training ? "Queuing…" : "Retrain now"}
            </Button>
          ) : null}
        </div>

        <div className="space-y-2">
          <h1 className="text-xl font-semibold text-foreground">{guide.label}</h1>
          <p className="font-mono text-xs text-muted-foreground">{modelName}</p>
          <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">{guide.summary}</p>
        </div>

        {isPlanned ? (
          <EmptyState
            iconSlot={
              <span className="flex h-16 w-16 items-center justify-center rounded-xl bg-warning/10">
                <ChartLineUp className="h-8 w-8 text-warning" weight="duotone" aria-hidden />
              </span>
            }
            title={`${guide.label} — not yet active`}
            description={plainDecisionReasoning(guide.dataExplainer || activationRequirement)}
          />
        ) : null}

        <Tabs defaultValue="overview">
          <TabsList className="flex w-full flex-wrap justify-start">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="performance">Performance</TabsTrigger>
            <TabsTrigger value="readiness">Training readiness</TabsTrigger>
            <TabsTrigger value="impact">Business impact</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="mt-6 space-y-4">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-xl border border-border/70 bg-secondary/20 p-4 text-sm">
                <p className="font-medium text-foreground">Why this matters</p>
                <p className="mt-2 leading-relaxed text-muted-foreground">{guide.whyItMatters}</p>
              </div>
              <div className="rounded-xl border border-border/70 bg-secondary/20 p-4 text-sm">
                <p className="font-medium text-foreground">About the data gate</p>
                <p className="mt-2 leading-relaxed text-muted-foreground">{guide.dataExplainer}</p>
                {guide.howToFeed ? (
                  <p className="mt-2 leading-relaxed text-muted-foreground">
                    <span className="font-medium text-foreground">How to feed it: </span>
                    {guide.howToFeed}
                  </p>
                ) : null}
                <p className="mt-2 text-xs text-muted-foreground">
                  The number is a minimum quality gate, not a max. You can’t raise or lower it here — keep
                  connecting sources and using the product so signals grow past the gate.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" asChild>
                    <Link href={APP_ROUTES.models}>Add custom models</Link>
                  </Button>
                  <Button size="sm" variant="ghost" asChild>
                    <Link href={APP_ROUTES.training}>Training</Link>
                  </Button>
                </div>
              </div>
            </div>
            <StatsGrid columns={3}>
              <StatCard label="Model type" value={readString(catalogEntry.model_type, "—").replace(/_/g, " ")} />
              <StatCard
                label="Advisory only"
                value={statusEntry?.advisory_only ? "Yes — recommends, doesn’t auto-act" : "No"}
                variant="info"
              />
              <StatCard
                label="Fallback when untrained"
                value={readString(statusEntry?.fallback, readString(catalogEntry.fallback, "—")).replace(
                  /_/g,
                  " ",
                )}
              />
            </StatsGrid>
            {!isPlanned ? (
              <div className="rounded-xl border border-dashed border-border bg-secondary/30 p-4 text-sm text-muted-foreground">
                <p className="font-medium text-foreground">Activation checklist</p>
                <ul className="mt-2 list-disc space-y-1 pl-5">
                  <li>{readString(catalogEntry.min_data, guide.dataExplainer)}</li>
                  <li>
                    Examples collected: {signalsAvailable} / {minRequired} (gate, not ceiling)
                  </li>
                  <li>Status: {readinessStatus.replace(/_/g, " ")}</li>
                </ul>
              </div>
            ) : null}
          </TabsContent>

          <TabsContent value="performance" className="mt-6 space-y-4">
            {readString(modelPerformance.status) === "insufficient_data" ? (
              <EmptyState
                title="Not enough predictions measured yet"
                description="This appears once sufficient outcome data accumulates for this model."
              />
            ) : (
              <StatsGrid columns={3}>
                <StatCard label="Evaluation status" value={readString(modelPerformance.status, "—")} />
                <StatCard label="Samples" value={readNumber(modelPerformance.samples, 0)} />
                <StatCard
                  label="Recommendation approval"
                  value={formatPercent(evaluations?.recommendation_approval_rate as number | null)}
                />
              </StatsGrid>
            )}
          </TabsContent>

          <TabsContent value="readiness" className="mt-6 space-y-4">
            {progress == null ? (
              <p className="text-sm text-muted-foreground">
                This model isn’t trainable for your org yet — it’s on the platform roadmap or disabled.
              </p>
            ) : (
              <>
                <Progress value={progress} className="h-2" />
                <p className="text-sm text-muted-foreground tabular-nums">
                  {signalsAvailable} / {minRequired} examples toward the training gate ·{" "}
                  {readinessStatus.replace(/_/g, " ")}
                </p>
                <p className="text-xs text-muted-foreground">{guide.dataExplainer}</p>
              </>
            )}
          </TabsContent>

          <TabsContent value="impact" className="mt-6 space-y-4">
            <StatsGrid columns={3}>
              <StatCard label="Linked outcome events" value={recentEvents.length} />
              <StatCard label="Avg confidence" value={formatScore(readNumber(outcomes?.avg_confidence, NaN) || null)} />
              <StatCard label="Departments" value={(catalogEntry.use_cases as string[] | undefined)?.length ?? "—"} />
            </StatsGrid>
            {recentEvents.length === 0 ? (
              <p className="text-sm text-muted-foreground">No outcome events linked to this model in the selected period.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {recentEvents.slice(0, 8).map((row, index) => (
                  <li key={String(row.id ?? index)} className="rounded-lg border border-border/60 px-3 py-2">
                    {readString(row.outcome_event, "event").replace(/_/g, " ")} ·{" "}
                    {readString(row.created_at, "—")}
                  </li>
                ))}
              </ul>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  )
}
