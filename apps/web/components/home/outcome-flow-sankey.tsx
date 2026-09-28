"use client"

import { useMemo } from "react"
import useSWR from "swr"
import { EChartsSankeyChart, type ChartConfig, type SankeyData } from "@/components/evilcharts/charts/echarts-sankey-chart"
import { workflowsApi } from "@/lib/api"
import { connectorVendorKey, formatVendorLabel } from "@/lib/connectors"
import { cn } from "@/lib/utils"

type ConnectorOutcome = { connector: string; pass: number; fail: number; cancel: number; pass_rate: number | null }

type OpsSummary = {
  window_hours?: number
  totals?: { pass: number; fail: number; cancel: number }
  by_connector?: ConnectorOutcome[]
  event_count?: number
}

const MAX_CONNECTORS = 6

const RESULTS = [
  { key: "passed", field: "pass", label: "Passed", light: "#239b75", dark: "#2fbf8f" },
  { key: "failed", field: "fail", label: "Failed", light: "#b3403f", dark: "#e07272" },
  { key: "cancelled", field: "cancel", label: "Cancelled", light: "#8a8f94", dark: "#6b7075" },
] as const

/**
 * Connector -> result flow of governed executions (ops-summary, 24h window).
 * Counts only: the outcome ledger carries no revenue attribution, so no currency
 * is shown. Source and connector are independent marginals and are not chained.
 */
export function OutcomeFlowSankey({ className }: { className?: string }) {
  const { data, error, isLoading } = useSWR(
    ["execution-outcomes-ops-summary"],
    () => workflowsApi.executionOutcomesOpsSummary(),
    { revalidateOnFocus: false, refreshInterval: 60_000 },
  )
  const summary = data as OpsSummary | undefined

  const rows = useMemo(
    () =>
      (summary?.by_connector ?? [])
        .filter((row) => row.connector && row.pass + row.fail + row.cancel > 0)
        .sort((a, b) => b.pass + b.fail + b.cancel - (a.pass + a.fail + a.cancel))
        .slice(0, MAX_CONNECTORS),
    [summary],
  )

  const { chartData, config } = useMemo(() => {
    const config: ChartConfig = {}
    const nodes: SankeyData["nodes"] = []
    const links: SankeyData["links"] = []
    rows.forEach((row, i) => {
      const key = `src${i}`
      config[key] = { label: formatVendorLabel(connectorVendorKey(row.connector)), colors: { light: ["#5b6168"], dark: ["#9aa0a6"] } }
      nodes.push({ name: key })
    })
    const resultIndex = new Map<string, number>()
    for (const result of RESULTS) {
      if (!rows.some((row) => row[result.field] > 0)) continue
      config[result.key] = { label: result.label, colors: { light: [result.light], dark: [result.dark] } }
      resultIndex.set(result.key, nodes.length)
      nodes.push({ name: result.key })
    }
    rows.forEach((row, i) => {
      for (const result of RESULTS) {
        const target = resultIndex.get(result.key)
        if (target != null && row[result.field] > 0) links.push({ source: i, target, value: row[result.field] })
      }
    })
    return { chartData: { nodes, links }, config }
  }, [rows])

  const hours = summary?.window_hours ?? 24
  const events = summary?.event_count ?? 0
  const hasFlow = rows.length > 0

  return (
    <section
      aria-labelledby="outcome-flow-heading"
      data-review-surface="outcome-flow"
      className={cn("border-t border-[color:var(--g-border-subtle)] pt-4", className)}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id="outcome-flow-heading" className="text-[13px] font-semibold text-foreground">
          Execution outcomes by system
        </h3>
        <span className="text-[11.5px] text-muted-foreground">
          {isLoading ? "Loading" : error ? "Unavailable" : `${events} governed executions · last ${hours}h · counts, not value`}
        </span>
      </div>

      {hasFlow ? (
        <>
          <EChartsSankeyChart
            data={chartData}
            config={config}
            className="mt-3 h-[260px] w-full"
            nodeWidth={8}
            nodePadding={22}
            linkCurvature={0.5}
            animationType="none"
          >
            <EChartsSankeyChart.Node radius={2}>
              <EChartsSankeyChart.NodeLabel position="outside" showValues />
            </EChartsSankeyChart.Node>
            <EChartsSankeyChart.Link variant="target" />
            <EChartsSankeyChart.Tooltip roundness="sm" />
          </EChartsSankeyChart>
          <table className="sr-only">
            <caption>Execution outcomes by connector, last {hours} hours</caption>
            <thead>
              <tr>
                <th scope="col">System</th>
                <th scope="col">Passed</th>
                <th scope="col">Failed</th>
                <th scope="col">Cancelled</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.connector}>
                  <th scope="row">{formatVendorLabel(connectorVendorKey(row.connector))}</th>
                  <td>{row.pass}</td>
                  <td>{row.fail}</td>
                  <td>{row.cancel}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : (
        <p className="mt-2 text-[12px] text-muted-foreground">
          {error
            ? "Outcome ledger unavailable."
            : isLoading
              ? "Loading outcomes."
              : "No connector executions recorded in this window. Flow appears once governed actions run."}
        </p>
      )}
    </section>
  )
}
