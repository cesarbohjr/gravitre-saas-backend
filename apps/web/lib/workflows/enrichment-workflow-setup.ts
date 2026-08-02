/**
 * Canonical Apollo → Clay → HubSpot enrichment setup for the workflow canvas.
 * Matches marketplace MSP enrichment steps and fills agents + instructions.
 *
 * Also stamps ``param_sources`` with ``from_step`` wiring so runs do not depend
 * on agents "setting" ``$clay_records`` / ``$enriched_records`` run parameters.
 */
import type { CanvasWorkflowNode } from "@/lib/workflows/builder-persistence"

export const LEAD_ENRICHMENT_AGENT_HINTS = [
  "lead enrichment coordinator",
  "lead-enrichment-coordinator",
  "msp prospecting coordinator",
  "enrichment",
] as const

export type BuilderAgentRef = {
  id: string
  name: string
  role?: string
  capabilities?: string[]
  config?: Record<string, unknown> | null
}

const APOLLO_LIST_INSTRUCTION =
  'Call apollo.lists.list. Prefer list name "MSP Prospects" (or install variable APOLLO_LIST_NAME). ' +
  "Return list ids, names, and contact_count for the next step."

const APOLLO_SEARCH_INSTRUCTION =
  'Call apollo.contacts.search for the MSP Prospects list (list_name="MSP Prospects" or APOLLO_LIST_NAME). ' +
  "Return contacts with email, name, company, title, and LinkedIn URL when available. " +
  "The tool stamps a ``records`` array for Clay push / HubSpot sync."

const APOLLO_POPULATE_TASK =
  'Using apollo.lists.list and apollo.contacts.search results for list "MSP Prospects" ' +
  "(or install variable APOLLO_LIST_NAME): If contact_count is 0 / contacts empty, prospect with " +
  "apollo.people.search, create Apollo contacts when needed (apollo.contacts.create), then add them via " +
  'apollo.lists.add (entity_ids + label_names=["MSP Prospects"], modality=contacts). If the list is ' +
  "already populated, confirm contact records are ready for Clay. Downstream connector steps read " +
  "``records`` from Apollo search outputs automatically — do not rely on setting run parameters. " +
  "Do not call hubspot.lists.add_contact here — membership is a dedicated step."

const CLAY_PUSH_INSTRUCTION =
  "Call clay.leads.push with the ``records`` array from the Apollo contacts search step. " +
  "Confirm push acceptance and any table/workbook identifiers for the pull step."

const CLAY_OUTPUT_INSTRUCTION =
  "Call clay.workflows.output.get for the enrichment job started upstream. " +
  "Pass through / normalize the upstream ``records`` array for HubSpot CRM sync."

const CLAY_CRM_SYNC_INSTRUCTION =
  "Call clay.crm.sync with records from the Clay outputs step, crm=hubspot, and " +
  "crm_connector_id from the active HubSpot connector. Create or update HubSpot contacts; " +
  "pass resulting contact ids to the list-membership step."

const HUBSPOT_LIST_TASK =
  'Using the HubSpot contacts created by clay.crm.sync, add each contact to the existing HubSpot static list ' +
  '"MSPs" via hubspot.lists.add_contact (list_id from install variable HUBSPOT_LIST_ID). ' +
  "Skip records missing contact_id. Summarize added and skipped counts."

type SetupRule = {
  match: RegExp
  kind: "task" | "agent" | "connector"
  vendor?: string
  selectedAction?: string
  instruction?: string
  task?: string
  agentHints?: readonly string[]
  /** Logical role used to wire from_step bindings after setup. */
  role?:
    | "apollo_lists"
    | "apollo_search"
    | "apollo_populate"
    | "clay_push"
    | "clay_outputs"
    | "crm_sync"
    | "hubspot_list"
}

const RULES: SetupRule[] = [
  {
    match: /list\s+apollo\s+contact\s+lists/i,
    kind: "connector",
    vendor: "apollo",
    selectedAction: "lists.list",
    instruction: APOLLO_LIST_INSTRUCTION,
    role: "apollo_lists",
  },
  {
    match: /search\s+apollo\s+contact/i,
    kind: "connector",
    vendor: "apollo",
    selectedAction: "contacts.search",
    instruction: APOLLO_SEARCH_INSTRUCTION,
    role: "apollo_search",
  },
  {
    match: /populate\s+apollo\s+list|prepare\s+clay/i,
    kind: "agent",
    task: APOLLO_POPULATE_TASK,
    agentHints: LEAD_ENRICHMENT_AGENT_HINTS,
    role: "apollo_populate",
  },
  {
    match: /push\s+leads\s+to\s+clay/i,
    kind: "connector",
    vendor: "clay",
    selectedAction: "leads.push",
    instruction: CLAY_PUSH_INSTRUCTION,
    role: "clay_push",
  },
  {
    match: /pull\s+clay\s+enriched/i,
    kind: "connector",
    vendor: "clay",
    selectedAction: "workflows.output.get",
    instruction: CLAY_OUTPUT_INSTRUCTION,
    role: "clay_outputs",
  },
  {
    match: /sync\s+enriched\s+records/i,
    kind: "connector",
    vendor: "clay",
    selectedAction: "crm.sync",
    instruction: CLAY_CRM_SYNC_INSTRUCTION,
    role: "crm_sync",
  },
  {
    match: /add\s+contacts\s+to\s+hubs/i,
    kind: "agent",
    task: HUBSPOT_LIST_TASK,
    agentHints: LEAD_ENRICHMENT_AGENT_HINTS,
    role: "hubspot_list",
  },
]

function pickAgent(agents: BuilderAgentRef[], hints: readonly string[]): BuilderAgentRef | null {
  const lowered = agents.map((a) => ({
    agent: a,
    blob: [
      a.name,
      a.role,
      ...(a.capabilities || []),
      String((a.config as { slug?: string } | null)?.slug || ""),
    ]
      .join(" ")
      .toLowerCase(),
  }))
  for (const hint of hints) {
    const hit = lowered.find((row) => row.blob.includes(hint.toLowerCase()))
    if (hit) return hit.agent
  }
  // Prefer sales/enrichment-capable agents before falling back.
  const salesLike = lowered.find((row) =>
    /enrich|prospect|apollo|clay|hubspot|sales/.test(row.blob),
  )
  return salesLike?.agent ?? agents[0] ?? null
}

export function isEnrichmentWorkflowCanvas(nodes: Array<{ name?: string; type?: string; vendor?: string }>): boolean {
  const blob = nodes.map((n) => `${n.name || ""} ${n.vendor || ""} ${n.type || ""}`).join(" ").toLowerCase()
  const hasApollo = blob.includes("apollo")
  const hasClay = blob.includes("clay")
  const hasHubspot = blob.includes("hubspot") || blob.includes("hubs")
  return hasApollo && hasClay && hasHubspot
}

export type EnrichmentSetupResult = {
  nodes: CanvasWorkflowNode[]
  changed: boolean
  filledInstructions: number
  boundAgents: number
  convertedTasks: number
  agentName: string | null
}

function fromStep(stepId: string, path: string[]): { from_step: string; path: string[] } {
  return { from_step: stepId, path }
}

/** Stamp durable from_step param_sources once node roles are known. */
function wireEnrichmentParamSources(
  nodes: CanvasWorkflowNode[],
  roles: Map<string, SetupRule["role"]>,
): { nodes: CanvasWorkflowNode[]; changed: boolean } {
  const idByRole = new Map<NonNullable<SetupRule["role"]>, string>()
  for (const node of nodes) {
    const role = roles.get(node.id)
    if (role) idByRole.set(role, node.id)
  }
  const searchId = idByRole.get("apollo_search")
  const pushId = idByRole.get("clay_push")
  const outputsId = idByRole.get("clay_outputs")
  const syncId = idByRole.get("crm_sync")
  if (!searchId && !pushId && !outputsId && !syncId) {
    return { nodes, changed: false }
  }

  let changed = false
  const next = nodes.map((node) => {
    const role = roles.get(node.id)
    if (!role) return node
    const existing =
      (node.config?.param_sources as Record<string, unknown> | undefined) ||
      (node.config?.paramSources as Record<string, unknown> | undefined) ||
      {}
    let paramSources = { ...existing }
    let localChanged = false

    if (role === "apollo_search" && !paramSources.list_name) {
      paramSources = { ...paramSources, list_name: "MSP Prospects" }
      localChanged = true
    }
    if (role === "clay_push" && searchId) {
      const records = paramSources.records as { from_step?: string } | string | undefined
      if (!records || typeof records === "string" || !records.from_step) {
        paramSources = { ...paramSources, records: fromStep(searchId, ["records"]) }
        localChanged = true
      }
    }
    if (role === "clay_outputs" && pushId) {
      const records = paramSources.records as { from_step?: string } | string | undefined
      if (!records || typeof records === "string" || !records.from_step) {
        paramSources = { ...paramSources, records: fromStep(pushId, ["records"]) }
        localChanged = true
      }
    }
    if (role === "crm_sync") {
      const nextSources = { ...paramSources }
      const records = nextSources.records as { from_step?: string } | string | undefined
      const recordsSource = outputsId || pushId || searchId
      if (recordsSource && (!records || typeof records === "string" || !records.from_step)) {
        nextSources.records = fromStep(recordsSource, ["records"])
        localChanged = true
      }
      if (!nextSources.crm) {
        nextSources.crm = "hubspot"
        localChanged = true
      }
      if (!nextSources.crm_connector_id) {
        nextSources.crm_connector_id = "$hubspot_connector_id"
        localChanged = true
      }
      paramSources = nextSources
    }

    if (!localChanged) return node
    changed = true
    return {
      ...node,
      config: {
        ...(node.config || {}),
        param_sources: paramSources,
        paramSources,
      },
    }
  })
  return { nodes: next, changed }
}

/** Fill missing agent bindings + instructions for Apollo/Clay/HubSpot enrichment canvases. */
export function applyEnrichmentWorkflowSetup(
  nodes: CanvasWorkflowNode[],
  agents: BuilderAgentRef[],
): EnrichmentSetupResult {
  if (!isEnrichmentWorkflowCanvas(nodes)) {
    return {
      nodes,
      changed: false,
      filledInstructions: 0,
      boundAgents: 0,
      convertedTasks: 0,
      agentName: null,
    }
  }

  let filledInstructions = 0
  let boundAgents = 0
  let convertedTasks = 0
  let agentName: string | null = null
  let changed = false
  const roles = new Map<string, SetupRule["role"]>()

  const next = nodes.map((node) => {
    const rule = RULES.find((r) => r.match.test(node.name || ""))
    if (!rule) return node
    if (rule.role) roles.set(node.id, rule.role)

    let updated: CanvasWorkflowNode = { ...node, config: { ...(node.config || {}) } }

    if (rule.kind === "agent") {
      const hints = rule.agentHints || LEAD_ENRICHMENT_AGENT_HINTS
      const agent = pickAgent(agents, hints)
      const existingId = String(updated.config?.agent_id || updated.config?.agentId || "")
      if (agent && !existingId) {
        updated = {
          ...updated,
          config: {
            ...updated.config,
            agent_id: agent.id,
            agentId: agent.id,
            agent_name: agent.name,
          },
        }
        boundAgents += 1
        changed = true
        agentName = agent.name
      } else if (agent) {
        agentName = agent.name
      }
      const existingTask = String(updated.config?.task || updated.description || "")
      if (rule.task && existingTask.trim().length < 40) {
        updated = {
          ...updated,
          description: rule.task,
          config: { ...updated.config, task: rule.task },
        }
        filledInstructions += 1
        changed = true
      } else if (rule.task && /\$clay_records|\$enriched_records/.test(existingTask)) {
        // Upgrade stale "set $clay_records" agent copy to from_step-aware wording.
        updated = {
          ...updated,
          description: rule.task,
          config: { ...updated.config, task: rule.task },
        }
        filledInstructions += 1
        changed = true
      }
      return updated
    }

    // Task or connector-style enrichment steps — prefer connector typing when vendor known.
    if (rule.vendor && (updated.type === "task" || updated.type === "tool" || updated.type === "connector")) {
      if (updated.type !== "connector") {
        updated = { ...updated, type: "connector" }
        convertedTasks += 1
        changed = true
      }
      if (!updated.vendor) {
        updated = { ...updated, vendor: rule.vendor }
        changed = true
      }
      if (rule.selectedAction && !updated.selectedAction) {
        const actionKey = `${rule.vendor}.${rule.selectedAction}`
        updated = {
          ...updated,
          selectedAction: rule.selectedAction,
          config: {
            ...updated.config,
            action: actionKey,
            selectedAction: rule.selectedAction,
            selected_action: rule.selectedAction,
            vendor: rule.vendor,
            connector: rule.vendor,
          },
        }
        changed = true
      }
    }

    const existingInstruction = String(
      updated.config?.instruction || updated.config?.instructions || updated.description || "",
    )
    if (rule.instruction && existingInstruction.trim().length < 40) {
      updated = {
        ...updated,
        description: rule.instruction,
        config: {
          ...updated.config,
          instruction: rule.instruction,
          instructions: rule.instruction,
        },
      }
      filledInstructions += 1
      changed = true
    } else if (
      rule.instruction &&
      /\$clay_records|\$enriched_records|\$hubspot_connector_id/.test(existingInstruction)
    ) {
      updated = {
        ...updated,
        description: rule.instruction,
        config: {
          ...updated.config,
          instruction: rule.instruction,
          instructions: rule.instruction,
        },
      }
      filledInstructions += 1
      changed = true
    }
    return updated
  })

  const wired = wireEnrichmentParamSources(next, roles)
  return {
    nodes: wired.nodes,
    changed: changed || wired.changed,
    filledInstructions,
    boundAgents,
    convertedTasks,
    agentName,
  }
}

export function requiredEnrichmentConnectors(nodes: Array<{ name?: string; vendor?: string; type?: string }>): string[] {
  if (!isEnrichmentWorkflowCanvas(nodes)) return []
  return ["apollo", "clay", "hubspot"]
}
