"use client"

import { useState } from "react"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { PageHeader } from "@/components/gravitre/page-header"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { intelligenceApi } from "@/lib/api"
import { SURFACE_COPY } from "@/lib/surface-copy"

const copy = SURFACE_COPY.pages.predictive

const DOMAINS = ["sales", "support", "operations", "finance", "marketing"] as const

export default function PredictiveOpsPage() {
  const [domain, setDomain] = useState<(typeof DOMAINS)[number]>("support")
  const { data, isLoading, error } = useSWR(
    ["intelligence/predictive-ops", domain],
    () => intelligenceApi.predictiveOpsDomain(domain),
    { refreshInterval: 60_000 },
  )
  const predictions = (data?.predictions as Array<Record<string, unknown>>) || []

  return (
    <AppShell title={copy.title}>
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <PageHeader title={copy.title} description={copy.description} />
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">Domain pack</span>
        <Select value={domain} onValueChange={(value) => setDomain(value as (typeof DOMAINS)[number])}>
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
      </div>
      {isLoading ? <p className="text-sm text-muted-foreground">Loading domain predictions…</p> : null}
      {error ? <p className="text-sm text-destructive">Unable to load predictive ops for this domain.</p> : null}
      <div className="grid gap-4 md:grid-cols-2">
        {predictions.map((row) => {
          const status = String(row.status || "unknown")
          const model = String(row.model || "model")
          return (
            <Card key={model}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between gap-2">
                  <CardTitle className="text-base font-medium">{model.replace(/_/g, " ")}</CardTitle>
                  <Badge variant={status === "ok" ? "default" : "secondary"}>{status}</Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                {row.reason ? <p>{String(row.reason)}</p> : null}
                {row.risk_score != null ? (
                  <p>
                    Risk score: <span className="font-medium text-foreground">{String(row.risk_score)}</span>
                  </p>
                ) : null}
                {row.data_gate ? (
                  <p>
                    Data gate: {String((row.data_gate as Record<string, unknown>).current ?? 0)} /{" "}
                    {String((row.data_gate as Record<string, unknown>).required ?? "?")}
                  </p>
                ) : null}
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
    </AppShell>
  )
}
