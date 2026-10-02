"use client"
import { DepartmentWorkspace } from "@/components/marketplace/department-workspace"
import type { DepartmentWorkspace as Workspace } from "@/lib/marketplace3"
import fixtures from "../fixtures.json"

const base = fixtures["revenue-operations-3"]
const workspace: Workspace = {
  ...base,
  install: { id: "fixture", version: 1, pilot: true, agentIds: ["fixture-agent"], workflowIds: ["fixture-flow"], capabilityPackageIds: [], plays: [{ playKey: base.contract.plays[0].key, workflowId: "fixture-flow" }] },
  measurements: [1, 2, 3].map(day => ({ evidenceId: `fixture-${day}`, metricKey: base.contract.dashboard.metrics[0].kpi_key, playKey: base.contract.plays[0].key, baselineValue: 30, resultValue: 30 - day * 5, measuredAt: `2026-09-0${day}T12:00:00Z`, verificationMethod: "Screenshot fixture only", sourceRecords: [{ system: "fixture", record_type: "sample", record_id: `${day}` }] })),
}
export default function MeasuredShot() {
  return <main className="mx-auto max-w-7xl p-4 sm:p-6"><p className="mb-5 text-sm text-muted-foreground">Screenshot fixture · sample measurements only · no production proof</p><DepartmentWorkspace workspace={workspace} /></main>
}
