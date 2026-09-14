"use client"

import { useMemo, useState } from "react"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { IntelligenceShell } from "@/components/intelligence/shell"
import { useIntelligenceSnapshot } from "@/lib/intelligence/use-intelligence-snapshot"
import { isSnapshotMetricsReady } from "@/lib/intelligence/snapshot-state"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { ConfidenceBadge } from "@/components/intelligence/confidence-badge"

const copy = SURFACE_COPY.pages.predictive

const DOMAINS = ["sales", "support", "operations", "finance", "marketing", "customer_success"] as const

type CanonicalPredictionRow = {
  id: string
  businessStatement: string
  department?: string | null
  confidence?: number | null
  status?: string
}

export default function PredictiveOpsPage() {
  const [domain, setDomain] = useState<(typeof DOMAINS)[number]>("support")
  const {
    data: pageContext,
    loadState,
    generatedAt,
    isValidating,
    mutate,
    error,
  } = useIntelligenceSnapshot({
    activeLens: "predicts",
    swrKeySuffix: domain,
  })
  const isLoading = !isSnapshotMetricsReady(loadState) && loadState !== "ERROR"

  const predictions = useMemo(() => {
    const raw = (pageContext?.snapshot.predictions ?? []) as CanonicalPredictionRow[]
    const domainNorm = domain.replace("_", " ").toLowerCase()
    return raw.filter((row) => {
      const dept = String(row.department ?? "").toLowerCase().replace("_", " ")
      return !dept || dept.includes(domainNorm) || domainNorm.includes(dept)
    })
  }, [pageContext?.snapshot.predictions, domain])

  const activeCount = isSnapshotMetricsReady(loadState)
    ? (pageContext?.metrics.predictions.activePredictions ??
      pageContext?.snapshot.metrics.predictions.activePredictions ??
      predictions.length)
    : null

  return (
    <AppShell title={copy.title}>
      <div className="mx-auto max-w-6xl space-y-6 p-6">
        <GravitrePageHeader
          title={copy.title}
          description={copy.description}
          icon={<NucleoIntelligence className="h-5 w-5" />}
        />
        <IntelligenceShell
          activeTab="predictions"
          loadState={loadState}
          generatedAt={generatedAt}
          isValidating={isValidating}
          onRefresh={() => mutate()}
          filters={
            <>
              <span className="text-sm text-muted-foreground">Domain filter</span>
              <Select
                value={domain}
                onValueChange={(value) => setDomain(value as (typeof DOMAINS)[number])}
              >
                <SelectTrigger className="w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DOMAINS.map((item) => (
                    <SelectItem key={item} value={item}>
                      {item}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <span className="text-sm text-muted-foreground">
                {activeCount != null
                  ? `${activeCount} active prediction${activeCount === 1 ? "" : "s"}`
                  : "— active predictions"}
              </span>
            </>
          }
        >
        {isLoading ? <p className="text-sm text-muted-foreground">Loading predictions…</p> : null}
        {error ? <p className="text-sm text-destructive">Unable to load predictions.</p> : null}
        {!isLoading && !error && predictions.length === 0 ? (
          <p className="text-sm text-muted-foreground">No predictions for this domain right now.</p>
        ) : null}
        <div className="grid gap-4 md:grid-cols-2">
          {predictions.map((row) => (
            <Card key={row.id}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between gap-2">
                  <CardTitle className="text-base font-medium">{row.businessStatement}</CardTitle>
                  {row.confidence != null ? (
                    <ConfidenceBadge score={row.confidence} showScore />
                  ) : null}
                </div>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                {row.department ? (
                  <p>
                    Department: <span className="font-medium text-foreground">{row.department}</span>
                  </p>
                ) : null}
                {row.status ? (
                  <p>
                    Status: <span className="font-medium text-foreground">{row.status}</span>
                  </p>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
        </IntelligenceShell>
      </div>
    </AppShell>
  )
}
