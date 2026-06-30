"use client"

import { useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { ErrorState } from "@/components/gravitre/empty-state"
import { intelligenceApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { toast } from "sonner"
import { Gauge } from "@phosphor-icons/react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { formatPercent, readNumber } from "./shared"

type PerformanceMode = "speed_priority" | "balanced" | "accuracy_priority"

const MODE_OPTIONS: { value: PerformanceMode; label: string; hint: string }[] = [
  {
    value: "speed_priority",
    label: "Speed priority",
    hint: "Aggressive Tier 0 caching; validation on deep modes only.",
  },
  {
    value: "balanced",
    label: "Balanced",
    hint: "Default caching and validation on standard+ modes.",
  },
  {
    value: "accuracy_priority",
    label: "Accuracy priority",
    hint: "Disables Tier 0; full retrieval and validation on every mode.",
  },
]

export function PerformanceTab({ enabled }: { enabled: boolean }) {
  const [period, setPeriod] = useState<"1h" | "24h" | "7d">("24h")
  const [mode, setMode] = useState<PerformanceMode>("balanced")
  const [savingMode, setSavingMode] = useState(false)

  const { data: modeData, mutate: mutateMode } = useSWR(
    enabled ? "admin/intelligence/performance-mode" : null,
    () => intelligenceApi.performanceMode(),
    { revalidateOnFocus: false },
  )

  const {
    data: dashboard,
    error,
    isLoading,
    mutate,
  } = useSWR(enabled ? ["admin/intelligence/performance", period] : null, () =>
    intelligenceApi.performance({ period }),
  )

  useEffect(() => {
    if (modeData?.mode) {
      setMode(modeData.mode as PerformanceMode)
    }
  }, [modeData?.mode])

  const stageChart = useMemo(() => {
    const byStage = dashboard?.byStage ?? {}
    return Object.entries(byStage).map(([stage, stats]) => ({
      stage: stage.replace(/_/g, " "),
      avgMs: readNumber((stats as { avgMs?: number }).avgMs),
      p95Ms: readNumber((stats as { p95Ms?: number }).p95Ms),
    }))
  }, [dashboard?.byStage])

  if (error) {
    const message = error instanceof ApiError ? error.message : "Failed to load performance metrics."
    return <ErrorState title="Unable to load performance" description={message} onRetry={() => mutate()} />
  }

  const saveMode = async (next: PerformanceMode) => {
    setSavingMode(true)
    try {
      await intelligenceApi.updatePerformanceMode({ mode: next })
      setMode(next)
      toast.success("Performance mode updated")
      await mutateMode()
    } catch (saveError) {
      toast.error(saveError instanceof ApiError ? saveError.message : "Could not save performance mode")
    } finally {
      setSavingMode(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Gauge className="h-5 w-5 text-violet-500" weight="duotone" aria-hidden />
            <CardTitle>Latency vs accuracy</CardTitle>
          </div>
          <CardDescription>
            Controls Tier 0 instant answers and how often post-answer validation runs.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-3">
          {MODE_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              disabled={savingMode}
              onClick={() => void saveMode(option.value)}
              className={`rounded-lg border p-4 text-left transition-colors ${
                mode === option.value
                  ? "border-violet-500 bg-violet-500/5"
                  : "border-border hover:border-violet-500/40"
              }`}
            >
              <p className="text-sm font-medium">{option.label}</p>
              <p className="mt-1 text-xs text-muted-foreground">{option.hint}</p>
            </button>
          ))}
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center gap-2">
        <Label className="sr-only">Period</Label>
        {(["1h", "24h", "7d"] as const).map((value) => (
          <Button
            key={value}
            size="sm"
            variant={period === value ? "default" : "outline"}
            onClick={() => setPeriod(value)}
          >
            {value}
          </Button>
        ))}
      </div>

      {isLoading || !dashboard ? (
        <p className="text-sm text-muted-foreground">Loading performance metrics…</p>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard label="Avg response" value={`${readNumber(dashboard.avgTotalResponseMs)} ms`} />
            <MetricCard label="P95 response" value={`${readNumber(dashboard.p95TotalResponseMs)} ms`} />
            <MetricCard
              label="Avg cost / answer"
              value={`$${readNumber(dashboard.avgCostPerAnswerUsd).toFixed(4)}`}
            />
            <MetricCard label="Timeout rate" value={formatPercent(readNumber(dashboard.timeoutRate))} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Stage latency (avg ms)</CardTitle>
              </CardHeader>
              <CardContent className="h-64">
                {stageChart.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No pipeline samples in this period.</p>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={stageChart}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis dataKey="stage" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Bar dataKey="avgMs" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Cache hit rates</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {Object.entries(dashboard.cacheHitRate ?? {}).map(([key, rate]) => (
                  <div key={key} className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{key.replace(/_/g, " ")}</span>
                    <span className="font-medium tabular-nums">{formatPercent(readNumber(rate))}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      </CardContent>
    </Card>
  )
}
