"use client"

import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { intelligenceApi } from "@/lib/api"
import { Gauge, WarningCircle } from "@phosphor-icons/react"

function severityVariant(severity: string): "destructive" | "secondary" | "outline" {
  if (severity === "high") return "destructive"
  if (severity === "medium") return "secondary"
  return "outline"
}

export function BusinessImpactCard() {
  const { data, isLoading } = useSWR(
    "admin/intelligence/business-impact",
    () => intelligenceApi.businessImpact(),
    { revalidateOnFocus: false },
  )

  const score = data?.businessImpactScore
  const items = data?.revenueRiskItems ?? []

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Gauge className="h-5 w-5 text-primary" weight="duotone" aria-hidden />
            <CardTitle>Business Impact Score</CardTitle>
          </div>
          <CardDescription>
            Composite over pending optimization suggestions and outcome-linked learning.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <>
              <div className="flex items-end gap-3">
                <span className="text-4xl font-semibold tabular-nums">{score ?? "—"}</span>
                {data?.scoreLabel ? (
                  <Badge variant={score != null && score < 60 ? "destructive" : "secondary"}>
                    {data.scoreLabel.replace("_", " ")}
                  </Badge>
                ) : null}
              </div>
              {data?.dimensions ? (
                <dl className="grid grid-cols-3 gap-3 text-sm">
                  <div>
                    <dt className="text-muted-foreground">Revenue risk</dt>
                    <dd className="font-medium tabular-nums">{data.dimensions.revenueRisk}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Outcome health</dt>
                    <dd className="font-medium tabular-nums">{data.dimensions.outcomeHealth}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Operational load</dt>
                    <dd className="font-medium tabular-nums">{data.dimensions.operationalLoad}</dd>
                  </div>
                </dl>
              ) : null}
              <p className="text-xs text-muted-foreground text-pretty">{data?.scopeNote}</p>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <WarningCircle className="h-5 w-5 text-amber-500" weight="duotone" aria-hidden />
            <CardTitle>Revenue Risk Radar</CardTitle>
          </div>
          <CardDescription>
            Pending business signals from v10 suggestions and v8 outcome summaries.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No revenue-risk items pending review. Run optimization detection or wait for more outcome samples.
            </p>
          ) : (
            items.map((item) => (
              <div key={item.id} className="rounded-lg border border-border p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{item.title}</span>
                  <Badge variant={severityVariant(item.severity)}>{item.severity}</Badge>
                  <Badge variant="outline">{item.source.replace("_", " ")}</Badge>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{item.summary}</p>
                {item.explanation ? (
                  <p className="mt-2 text-xs text-muted-foreground text-pretty">{item.explanation}</p>
                ) : null}
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}
