/**
 * Workflow-scoped Meson alerts from the open canvas (readiness + connectors).
 * Complements org/API alerts which are filtered by workflowId.
 */
import type { MesonAlert } from "@/lib/api"
import type { CanvasWorkflowNode } from "@/lib/workflows/builder-persistence"
import { evaluateNodeReadiness } from "@/lib/workflows/builder-node-readiness"
import { resolveConnectorBind } from "@/lib/workflows/builder-connector-bind"
import {
  isEnrichmentWorkflowCanvas,
  requiredEnrichmentConnectors,
} from "@/lib/workflows/enrichment-workflow-setup"

export type OrgConnectorRef = {
  id?: string
  vendor?: string
  type?: string
  status?: string
}

function vendorKey(value: string | undefined): string {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[\s_]+/g, "-")
}

function isConnectedStatus(status: string | undefined): boolean {
  const s = String(status || "").toLowerCase()
  return s === "connected" || s === "active" || s === "healthy"
}

function canvasVendors(nodes: CanvasWorkflowNode[]): string[] {
  const vendors = new Set<string>()
  for (const node of nodes) {
    const bind = resolveConnectorBind({
      vendor: node.vendor,
      selectedAction: node.selectedAction,
      config: node.config,
    })
    if (bind.vendor) vendors.add(vendorKey(bind.vendor))
    const name = (node.name || "").toLowerCase()
    if (name.includes("apollo")) vendors.add("apollo")
    if (name.includes("clay")) vendors.add("clay")
    if (name.includes("hubspot") || name.includes("hubs")) vendors.add("hubspot")
    if (name.includes("slack")) vendors.add("slack")
    if (name.includes("gmail") || name.includes("google")) vendors.add("gmail")
  }
  if (isEnrichmentWorkflowCanvas(nodes)) {
    for (const v of requiredEnrichmentConnectors(nodes)) vendors.add(v)
  }
  return [...vendors]
}

/** Build alerts that are specific to the open workflow canvas. */
export function buildCanvasMesonAlerts(
  nodes: CanvasWorkflowNode[],
  orgConnectors: OrgConnectorRef[] = [],
  workflowId?: string,
): MesonAlert[] {
  const alerts: MesonAlert[] = []
  const dismissedPrefix = workflowId || "canvas"

  for (const node of nodes) {
    const readiness = evaluateNodeReadiness(node)
    if (readiness.ready) continue
    const kind =
      node.type === "agent"
        ? "Agent"
        : node.type === "connector"
          ? "Connector"
          : node.type === "task"
            ? "Task"
            : "Step"
    alerts.push({
      id: `canvas-ready-${dismissedPrefix}-${node.id}`,
      severity: node.type === "agent" || node.type === "connector" ? "warning" : "info",
      title: `${kind} incomplete: ${node.name || "Untitled"}`,
      message: readiness.summary,
      autoFixable: true,
      actionType: "select-node",
      actionTarget: node.id,
      fixLabel: "Open step",
    })
  }

  const needed = canvasVendors(nodes)
  const connected = new Set(
    orgConnectors
      .filter((c) => isConnectedStatus(c.status))
      .map((c) => vendorKey(c.vendor || c.type)),
  )
  for (const vendor of needed) {
    if (connected.has(vendor)) continue
    const existing = orgConnectors.find((c) => vendorKey(c.vendor || c.type) === vendor)
    const label = vendor.charAt(0).toUpperCase() + vendor.slice(1)
    alerts.push({
      id: `canvas-connector-missing-${dismissedPrefix}-${vendor}`,
      severity: "critical",
      title: `${label} connector required`,
      message: existing
        ? `${label} exists but is not connected — reconnect it so this workflow can run.`
        : `Connect ${label} before running this workflow. Nodes that call ${label} will fail until it is available.`,
      autoFixable: true,
      actionType: "navigate",
      actionTarget: existing?.id ? `/connectors/${existing.id}` : `/connectors?type=${vendor}`,
      fixLabel: existing ? "Reconnect" : "Connect",
    })
  }

  if (isEnrichmentWorkflowCanvas(nodes)) {
    const unboundAgents = nodes.filter((n) => {
      if (n.type !== "agent") return false
      return !String(n.config?.agent_id || n.config?.agentId || "").trim()
    })
    if (unboundAgents.length > 0) {
      alerts.push({
        id: `canvas-enrichment-agents-${dismissedPrefix}`,
        severity: "warning",
        title: "Bind Lead Enrichment Coordinator",
        message: `${unboundAgents.length} agent step(s) need the Lead Enrichment Coordinator (or MSP Prospecting Coordinator). Accept Meson’s setup suggestion or pick an agent on each step.`,
        autoFixable: true,
        actionType: "setup-enrichment",
        actionTarget: unboundAgents[0]?.id,
        fixLabel: "Set up agents",
      })
    }

    const thinInstructions = nodes.filter((n) => {
      const text = String(
        n.config?.task || n.config?.instruction || n.config?.instructions || n.description || "",
      ).trim()
      return text.length < 40
    })
    if (thinInstructions.length > 0) {
      alerts.push({
        id: `canvas-enrichment-instructions-${dismissedPrefix}`,
        severity: "warning",
        title: "Enrichment instructions incomplete",
        message: `${thinInstructions.length} step(s) are missing Apollo/Clay/HubSpot run instructions. Apply Meson’s enrichment setup to fill the canonical tasks.`,
        autoFixable: true,
        actionType: "setup-enrichment",
        actionTarget: thinInstructions[0]?.id,
        fixLabel: "Fill instructions",
      })
    }
  }

  // Prefer critical/warning first; cap so the panel stays scannable.
  const rank = (s: string) => (s === "critical" ? 0 : s === "warning" ? 1 : 2)
  return alerts.sort((a, b) => rank(a.severity) - rank(b.severity)).slice(0, 12)
}

/** Keep API alerts that belong to this workflow (or are connector auth for vendors in use). */
export function filterApiAlertsForWorkflow(
  alerts: MesonAlert[],
  workflowId: string | undefined,
  nodes: CanvasWorkflowNode[],
): MesonAlert[] {
  // When the API was called with workflowId, run-failure rows are already scoped — keep them.
  // Still drop unrelated connector auth for vendors not on this canvas.
  const vendors = new Set(canvasVendors(nodes))
  return alerts.filter((alert) => {
    const target = String(alert.actionTarget || "")
    if (workflowId && target.includes(`/workflows/${workflowId}`)) return true
    if (target.startsWith("/runs/")) return Boolean(workflowId)
    if (alert.id.startsWith("connector-auth-") || target.startsWith("/connectors")) {
      if (vendors.size === 0) return !workflowId
      const blob = `${alert.title} ${alert.message} ${target}`.toLowerCase()
      return [...vendors].some((v) => blob.includes(v))
    }
    // Failure-prediction UUID rows for this workflow
    if (workflowId && /^[0-9a-f-]{36}$/i.test(alert.id)) return true
    if (!workflowId) return true
    const blob = `${alert.title} ${alert.message}`.toLowerCase()
    return [...vendors].some((v) => blob.includes(v))
  })
}

/** Rotate tips vs insights for the Optimize section. */
export function rotateTipsAndInsights(
  items: Array<{ id: string; title: string; summary: string; category?: string }>,
  workflowId: string | undefined,
  *,
  tipCount = 1,
  insightCount = 1,
): { tips: typeof items; insights: typeof items } {
  const tips = items.filter((i) => (i.category || "").toLowerCase() === "tip")
  const insights = items.filter((i) => (i.category || "").toLowerCase() !== "tip")
  const seed = hashSeed(`${workflowId || "local"}-${hourBucket()}`)
  return {
    tips: pickRotated(tips.length ? tips : items, tipCount, seed),
    insights: pickRotated(insights.length ? insights : items, insightCount, seed + 17),
  }
}

function hourBucket(): string {
  const d = new Date()
  return `${d.getUTCFullYear()}-${d.getUTCMonth()}-${d.getUTCDate()}-${d.getUTCHours()}`
}

function hashSeed(input: string): number {
  let h = 0
  for (let i = 0; i < input.length; i += 1) {
    h = (h * 31 + input.charCodeAt(i)) >>> 0
  }
  return h
}

function pickRotated<T>(items: T[], count: number, seed: number): T[] {
  if (items.length === 0 || count <= 0) return []
  const start = seed % items.length
  const out: T[] = []
  for (let i = 0; i < Math.min(count, items.length); i += 1) {
    out.push(items[(start + i) % items.length])
  }
  return out
}
