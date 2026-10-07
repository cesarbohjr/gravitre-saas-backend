import {
  LAYER_BASE,
  edgeKey,
  type FlowLayerId,
  type FlowModel,
  type FlowNode,
} from "@/components/intelligence/overview/flow-model"

/**
 * Example data for the overview's "Example data" mode. Shown only when the
 * person picks it, always badged "Example", never mixed with live records.
 */

const LAYER_KEY: Record<string, FlowLayerId> = {
  S: "sources",
  K: "knowledge",
  L: "learning",
  M: "models",
  F: "forecasts",
}

const RAW: Array<[string, keyof typeof LAYER_KEY, string, string]> = [
  ["hubspot", "S", "HubSpot CRM", "Deals, contacts and companies, synced from HubSpot."],
  ["zendesk", "S", "Zendesk", "Support tickets and replies, synced from Zendesk."],
  ["postgres", "S", "Postgres warehouse", "Shipments, depots and delivery times from your warehouse."],
  ["platform", "S", "Team actions", "Approvals, corrections and runs your team does inside Gravitre. Every one is a lesson."],
  ["customer", "K", "Customer", "Accounts you ship for, joined across CRM, support and shipments."],
  ["deal", "K", "Deal", "Open and closed sales opportunities."],
  ["ticket", "K", "Ticket", "Support requests from customers."],
  ["shipment", "K", "Shipment", "Every load moving through your network."],
  ["depot", "K", "Depot", "Where freight is stored and dispatched from."],
  ["coldchain", "L", "Cold-chain routing", "Refrigerated freight should leave from Reno or Tacoma. Routing it elsewhere tends to end in a delay ticket."],
  ["support", "L", "Support load predicts churn", "Accounts whose ticket volume rises for three weeks renew less often."],
  ["enterprise", "L", "Enterprise lead mix", "New leads are shifting toward larger companies, which close slower but stay longer."],
  ["churn", "M", "Churn risk scorer", "Predicts which accounts may not renew in the next 90 days."],
  ["leadfit", "M", "Lead fit score", "Ranks new leads by how closely they match deals you have won."],
  ["router", "M", "Ticket router", "Sends each support ticket to the right queue."],
  ["renewals", "F", "Renewals at risk", "Accounts likely to churn next quarter."],
  ["pipeline", "F", "Qualified pipeline", "Expected value of the leads worth chasing."],
  ["volume", "F", "Ticket volume", "Support load expected next week, by queue."],
]

const EDGES = [
  "hubspot>customer", "hubspot>deal", "zendesk>ticket", "zendesk>customer", "postgres>shipment", "postgres>depot",
  "postgres>customer", "platform>ticket", "platform>deal", "platform>shipment", "customer>support", "ticket>support",
  "ticket>coldchain", "shipment>coldchain", "depot>coldchain", "deal>enterprise", "customer>enterprise", "support>churn",
  "support>router", "coldchain>router", "enterprise>leadfit", "customer>churn", "deal>leadfit", "ticket>router",
  "churn>renewals", "leadfit>pipeline", "router>volume", "churn>pipeline",
]

export type ExampleScenario = { path: string[]; text: string; feedback: boolean }

const ex = (id: string) => `ex:${id}`

export const EXAMPLE_FORWARD: ExampleScenario[] = [
  { path: ["platform", "ticket", "router", "volume"], text: "An agent triaged a new ticket with Ticket router" },
  { path: ["zendesk", "ticket", "support", "churn", "renewals"], text: "Acme Freight opened a third ticket this week. Churn risk nudged up." },
  { path: ["hubspot", "deal", "enterprise", "leadfit", "pipeline"], text: "Deal moved to Proposal in HubSpot. Lead fit rescored." },
  { path: ["postgres", "shipment", "coldchain", "router"], text: "Reefer load delayed at Fresno. Cold-chain routing reinforced." },
  { path: ["platform", "deal", "leadfit", "pipeline"], text: "A rep approved a lead handoff" },
  { path: ["hubspot", "customer", "churn", "renewals"], text: "Account health updated for Polar Logistics" },
  { path: ["postgres", "depot", "coldchain"], text: "Depot capacity refreshed from the warehouse" },
  { path: ["platform", "ticket", "support"], text: "A teammate corrected a ticket category" },
  { path: ["zendesk", "customer", "enterprise", "leadfit"], text: "Enterprise account asked about volume pricing" },
].map((s) => ({ ...s, path: s.path.map(ex), feedback: false }))

export const EXAMPLE_FEEDBACK: ExampleScenario[] = [
  { path: ["renewals", "churn", "support"], text: "Outcome: Acme Freight renewed. Churn model corrected itself." },
  { path: ["volume", "router", "coldchain"], text: "Outcome: ticket solved in the right queue. Routing confirmed." },
  { path: ["pipeline", "leadfit", "enterprise"], text: "Outcome: deal won. Lead fit learned what good looks like." },
].map((s) => ({ ...s, path: s.path.map(ex), feedback: true }))

export const EXAMPLE_NODE_IDS = RAW.map((r) => ex(r[0]))

export const EXAMPLE_REINFORCED: Record<string, number> = { [ex("coldchain")]: 14, [ex("support")]: 9, [ex("enterprise")]: 6 }
export const EXAMPLE_START = { signals: 1284, outcomes: 12, target: 50 }

/** Deterministic base edge weight, as in the design, so example lines vary in thickness. */
function baseWeight(i: number): number {
  return 1 + (((i * 37) % 10) / 10) * 1.6
}

export function buildExampleFlowModel(): FlowModel {
  const nodes: FlowNode[] = RAW.map(([id, layer, label, desc]) => {
    const layerId = LAYER_KEY[layer]
    const base = LAYER_BASE.find((l) => l.id === layerId)!
    return {
      id: ex(id),
      layer: layerId,
      label,
      desc,
      sub: "",
      href: base.href,
      scored: layerId === "forecasts" ? false : undefined,
    }
  })
  const edges = EDGES.map((k, i) => {
    const [a, b] = k.split(">")
    return { key: edgeKey(ex(a), ex(b)), a: ex(a), b: ex(b), weight: baseWeight(i), evidence: true }
  })
  return {
    example: true,
    layers: LAYER_BASE.map((l) => ({
      ...l,
      count: { sources: "4 sources", knowledge: "5 entities", learning: "3 learnings", models: "3 models", forecasts: "3 unscored" }[l.id],
    })),
    nodes,
    edges,
    events: [],
    learnings: ["coldchain", "support", "enterprise"].map((id) => {
      const node = nodes.find((n) => n.id === ex(id))!
      return { id, nodeId: node.id, label: node.label, desc: node.desc, reinforced: EXAMPLE_REINFORCED[node.id], confidence: null }
    }),
    stats: {
      signalsToday: EXAMPLE_START.signals,
      signalsSub: "Every sync, run and click that reached the core",
      connections: 0,
      connectionsSub: "Links that got more certain this session",
      outcomesFed: EXAMPLE_START.outcomes,
      outcomesTarget: EXAMPLE_START.target,
      forecastValue: "Calibrating",
      forecastNote: `${EXAMPLE_START.target - EXAMPLE_START.outcomes} outcomes until scoring starts`,
      forecastScored: false,
    },
    coreState: { label: "Learning", tone: "brand" },
    lastSignalAt: null,
    quiet: null,
  }
}
