import React from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { expect, it } from "vitest"
import { WorkflowFleetSummary } from "@/components/workflows/workflow-fleet-summary"
it("distinguishes unreported organization metrics from actual zeros", () => {
  const missing = renderToStaticMarkup(<WorkflowFleetSummary successRate={null} weeklyRuns={null} />)
  expect(missing.match(/Not reported/g)).toHaveLength(2)
  expect(missing).not.toContain(">0<")
  const zero = renderToStaticMarkup(<WorkflowFleetSummary successRate={0} weeklyRuns={0} />)
  expect(zero).toContain(">0%<"); expect(zero).toContain(">0<")
  expect(zero).not.toContain("Not reported")
})
it("labels totals independently of filters and keeps execution distinct from outcome verification", () => {
  const output = renderToStaticMarkup(<WorkflowFleetSummary successRate={97.4} weeklyRuns={42} />)
  expect(output).toContain("97%")
  expect(output).toContain(">42<")
  expect(output).toContain("independent of list filters")
  expect(output).toContain("does not establish a verified business outcome")
})
