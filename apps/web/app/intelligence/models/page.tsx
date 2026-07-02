"use client"

import useSWR from "swr"
import Link from "next/link"
import { ChartLineUp } from "@phosphor-icons/react"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { useAuth } from "@/lib/auth-context"
import { intelligenceApi, mlAdminApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { formatScore, modelStatusChipClass, readNumber, readString } from "@/lib/intelligence/helpers"

function dataSufficiencyProgress(
  modelName: string,
  status: string,
  readiness?: Record<string, unknown>,
): { value: number | null; label: string } {
  if (status.toUpperCase() === "PLANNED" || status.toUpperCase() === "DISABLED") {
    return { value: null, label: "Not active" }
  }
  const byModel = (readiness?.by_model as Record<string, Record<string, unknown>> | undefined) ?? {}
  const entry = byModel[modelName]
  if (!entry) return { value: null, label: "—" }
  const available = readNumber(entry.signals_available, 0)
  const required = readNumber(entry.min_required, 1)
  return {
    value: Math.min(100, Math.round((available / Math.max(required, 1)) * 100)),
    label: `${available} / ${required}`,
  }
}

export default function IntelligenceModelsPage() {
  const { user } = useAuth()
  const { data, error, isLoading, mutate } = useSWR(
    user ? "intelligence/models/catalog" : null,
    () => mlAdminApi.listCatalog(),
    { revalidateOnFocus: false },
  )
  const { data: readiness } = useSWR(user ? "intelligence/training-readiness" : null, () =>
    intelligenceApi.trainingReadiness(),
  )

  if (!user) {
    return (
      <AppShell title="Model Intelligence">
        <EmptyState title="Sign in required" description="Log in to view model intelligence profiles." />
      </AppShell>
    )
  }

  if (error) {
    return (
      <AppShell title="Model Intelligence">
        <ErrorState
          title="Unable to load models"
          description={error instanceof ApiError ? error.message : "Please try again."}
          onRetry={() => mutate()}
        />
      </AppShell>
    )
  }

  const catalog = data?.catalog ?? {}
  const orgStatus = data?.orgTrainingStatus ?? {}
  const names = Object.keys(catalog).sort()

  return (
    <AppShell title="Model Intelligence">
      <div className="space-y-6 p-4 md:p-6">
        <p className="text-sm text-muted-foreground text-pretty">
          Catalog models from Gravitre ML with honest TRAINED / PLANNED / DISABLED status and org training readiness.
        </p>

        {isLoading && !data ? (
          <p className="text-sm text-muted-foreground">Loading model catalog…</p>
        ) : names.length === 0 ? (
          <EmptyState title="No models in catalog" description="The ML catalog has not been configured for this org yet." />
        ) : (
          <div className="overflow-x-auto rounded-2xl border border-border/70">
            <table className="min-w-full text-sm">
              <thead className="border-b border-border bg-secondary/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">Model</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Use cases</th>
                  <th className="px-4 py-3">Data sufficiency</th>
                  <th className="px-4 py-3">Outcome score</th>
                  <th className="px-4 py-3">Last trained</th>
                </tr>
              </thead>
              <tbody>
                {names.map((name) => {
                  const entry = catalog[name] as Record<string, unknown>
                  const statusRow = orgStatus[name]
                  const status = readString(statusRow?.catalog_status, readString(entry.status, "PLANNED"))
                  const sufficiency = dataSufficiencyProgress(name, status, readiness)
                  return (
                    <tr key={name} className="border-b border-border/60 last:border-0">
                      <td className="px-4 py-3 font-medium">
                        <Link href={`/intelligence/models/${encodeURIComponent(name)}`} className="text-primary hover:underline">
                          {name}
                        </Link>
                      </td>
                      <td className="px-4 py-3 capitalize text-muted-foreground">
                        {readString(entry.model_type, "classifier").replace(/_/g, " ")}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline" className={modelStatusChipClass(status)}>
                          {status.toUpperCase() === "PLANNED" ? (
                            <ChartLineUp className="mr-1 h-3 w-3" weight="duotone" aria-hidden />
                          ) : null}
                          {status}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {Array.isArray(entry.use_cases) ? (entry.use_cases as string[]).slice(0, 2).join(", ") : "—"}
                      </td>
                      <td className="px-4 py-3">
                        {sufficiency.value == null ? (
                          <span className="text-muted-foreground">{sufficiency.label}</span>
                        ) : (
                          <div className="flex min-w-[120px] items-center gap-2">
                            <Progress value={sufficiency.value} className="h-2 flex-1" />
                            <span className="text-xs tabular-nums text-muted-foreground">{sufficiency.label}</span>
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 tabular-nums">{formatScore(null)}</td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {readString((readiness?.by_model as Record<string, Record<string, unknown>> | undefined)?.[name]?.last_trained_at, "—")}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppShell>
  )
}
