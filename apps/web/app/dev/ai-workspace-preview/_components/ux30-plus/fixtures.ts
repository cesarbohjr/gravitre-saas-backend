/**
 * Intelligence harness — contract-shaped mock fixtures.
 * MOCK DATA · Northwind Logistics · not live tenant / not production Knowledge Fabric.
 *
 * Entity/relationship shapes mirror org_entity_relationships + page-context graph
 * presentation needs. Lenses filter ONE canonical graph — no per-lens datasets.
 */

export const HARNESS_FIXTURE_LABEL =
  "MOCK DATA · Northwind Logistics · contract-shaped · not live telemetry"

export type HarnessLens = "knows" | "learns" | "predicts" | "acts" | "improves"

export type EntityKind = "account" | "contact" | "opportunity" | "ticket" | "product"

export type RelationshipStatus =
  | "confirmed"
  | "learned"
  | "predicted"
  | "contradicted"
  | "archived"

export type HarnessEntity = {
  id: string
  kind: EntityKind
  label: string
  sublabel?: string
  x: number
  y: number
  /** Lenses where this entity is emphasized (always present in canonical set) */
  lenses: HarnessLens[]
  sourceSystem?: string
  freshness?: string
}

export type HarnessRelationship = {
  id: string
  fromId: string
  toId: string
  type: string
  status: RelationshipStatus
  confidence: number | null
  /** Honest: null = unknown, not fabricated */
  evidence: string[]
  reason: string
  lenses: HarnessLens[]
  changedAt?: string
}

export type ChangeEventKind =
  | "new_relationship"
  | "changed_relationship"
  | "confirmed_knowledge"
  | "learned_knowledge"
  | "contradiction"
  | "archived_relationship"
  | "freshness_change"

export type HarnessChangeEvent = {
  id: string
  kind: ChangeEventKind
  title: string
  summary: string
  at: string
  entityIds: string[]
  relationshipId?: string
  evidence?: string
  lens: HarnessLens
}

/** Legacy aliases for Activity / foundation harness imports */
export type HarnessGraphNode = {
  id: string
  kind: string
  label: string
  sublabel?: string
  state?: "idle" | "active" | "learned" | "warning"
  x: number
  y: number
  lenses?: HarnessLens[]
  provenance?: string
  evidenceLabels?: string[]
}

export type HarnessGraphEdge = {
  id: string
  fromId: string
  toId: string
  label?: string
  edgeType?: string
  state?: "idle" | "active" | "learned"
  lenses?: HarnessLens[]
}

export type HarnessTraceStage = {
  id: string
  label: string
  status: "pending" | "running" | "waiting" | "verified" | "failed"
  summary: string
  durationMs?: number
  startedAt?: string
  evidence?: string[]
  actor?: string
}

export type HarnessOutcome = {
  id: string
  title: string
  status: "succeeded" | "failed" | "running"
  runId: string
  createdAt: string
  stages: HarnessTraceStage[]
}

export type HarnessPageContextMetrics = {
  knownEntities: number
  knownRelationships: number
  note: string
}

// ——— Canonical KG entities (I1 primary objects) ———

export const HARNESS_ENTITIES: HarnessEntity[] = [
  { id: "acct-acme", kind: "account", label: "Acme Corp", sublabel: "Account", x: 400, y: 200, lenses: ["knows", "learns", "predicts", "acts", "improves"], sourceSystem: "HubSpot", freshness: "2h" },
  { id: "acct-gold", kind: "account", label: "Gold Kist Inc.", sublabel: "Account", x: 220, y: 120, lenses: ["knows", "predicts"], sourceSystem: "HubSpot", freshness: "1d" },
  { id: "con-roderick", kind: "contact", label: "Roderick Deltoro", sublabel: "Contact", x: 580, y: 120, lenses: ["knows", "acts"], sourceSystem: "HubSpot", freshness: "3h" },
  { id: "con-sarah", kind: "contact", label: "Sarah Chen", sublabel: "Contact", x: 620, y: 280, lenses: ["knows", "learns"], sourceSystem: "Email", freshness: "5h" },
  { id: "opp-renewal", kind: "opportunity", label: "Acme Renewal Q3", sublabel: "Opportunity", x: 280, y: 300, lenses: ["knows", "predicts", "acts", "improves"], sourceSystem: "HubSpot", freshness: "4h" },
  { id: "tkt-latency", kind: "ticket", label: "Latency escalation", sublabel: "Ticket", x: 480, y: 340, lenses: ["knows", "learns", "acts"], sourceSystem: "Support", freshness: "40m" },
  { id: "prod-pro", kind: "product", label: "Gravitre Pro", sublabel: "Product", x: 160, y: 260, lenses: ["knows", "improves"], sourceSystem: "Catalog", freshness: "7d" },
]

export const HARNESS_RELATIONSHIPS: HarnessRelationship[] = [
  {
    id: "rel-works-roderick",
    fromId: "con-roderick",
    toId: "acct-acme",
    type: "works_at",
    status: "confirmed",
    confidence: 0.94,
    evidence: ["hubspot.contact.company", "email.domain_match"],
    reason: "CRM company association + matching email domain",
    lenses: ["knows", "acts"],
    changedAt: "3h ago",
  },
  {
    id: "rel-works-sarah",
    fromId: "con-sarah",
    toId: "acct-acme",
    type: "works_at",
    status: "learned",
    confidence: 0.71,
    evidence: ["email.signature", "thread.co_occurrence"],
    reason: "Learned from email signature; not CRM-confirmed",
    lenses: ["knows", "learns"],
    changedAt: "5h ago",
  },
  {
    id: "rel-owns-opp",
    fromId: "acct-acme",
    toId: "opp-renewal",
    type: "has_opportunity",
    status: "confirmed",
    confidence: 0.98,
    evidence: ["hubspot.deal.company"],
    reason: "Deal company lookup",
    lenses: ["knows", "predicts", "acts", "improves"],
    changedAt: "4h ago",
  },
  {
    id: "rel-ticket-acct",
    fromId: "tkt-latency",
    toId: "acct-acme",
    type: "about_account",
    status: "confirmed",
    confidence: 0.88,
    evidence: ["support.ticket.account_id"],
    reason: "Ticket account foreign key",
    lenses: ["knows", "learns", "acts"],
    changedAt: "40m ago",
  },
  {
    id: "rel-churn-risk",
    fromId: "opp-renewal",
    toId: "tkt-latency",
    type: "risk_signal",
    status: "predicted",
    confidence: 0.62,
    evidence: ["prediction.score", "open_ticket_pressure"],
    reason: "Model links open escalations to renewal risk",
    lenses: ["predicts", "learns"],
    changedAt: "28m ago",
  },
  {
    id: "rel-product",
    fromId: "opp-renewal",
    toId: "prod-pro",
    type: "for_product",
    status: "confirmed",
    confidence: 0.91,
    evidence: ["hubspot.deal.product"],
    reason: "Line item product",
    lenses: ["knows", "improves"],
    changedAt: "1d ago",
  },
  {
    id: "rel-gold-contradict",
    fromId: "con-roderick",
    toId: "acct-gold",
    type: "works_at",
    status: "contradicted",
    confidence: 0.22,
    evidence: ["stale_crm_row", "newer_acme_association"],
    reason: "Older CRM row contradicts current Acme association",
    lenses: ["knows", "learns"],
    changedAt: "2d ago",
  },
  {
    id: "rel-archived",
    fromId: "con-sarah",
    toId: "acct-gold",
    type: "mentioned_with",
    status: "archived",
    confidence: null,
    evidence: ["thread.co_occurrence"],
    reason: "Archived weak co-mention — not active knowledge",
    lenses: ["learns"],
    changedAt: "12d ago",
  },
]

export const HARNESS_CHANGE_EVENTS: HarnessChangeEvent[] = [
  {
    id: "ce-new",
    kind: "new_relationship",
    title: "New: Sarah Chen → Acme Corp",
    summary: "Learned works_at from email signature.",
    at: "5h ago",
    entityIds: ["con-sarah", "acct-acme"],
    relationshipId: "rel-works-sarah",
    evidence: "email.signature",
    lens: "learns",
  },
  {
    id: "ce-changed",
    kind: "changed_relationship",
    title: "Confidence up: Roderick → Acme",
    summary: "works_at confidence 0.81 → 0.94 after re-sync.",
    at: "3h ago",
    entityIds: ["con-roderick", "acct-acme"],
    relationshipId: "rel-works-roderick",
    evidence: "hubspot.contact.company",
    lens: "knows",
  },
  {
    id: "ce-confirmed",
    kind: "confirmed_knowledge",
    title: "Confirmed: Acme → Renewal Q3",
    summary: "Deal company association verified in CRM.",
    at: "4h ago",
    entityIds: ["acct-acme", "opp-renewal"],
    relationshipId: "rel-owns-opp",
    evidence: "hubspot.deal.company",
    lens: "knows",
  },
  {
    id: "ce-learned",
    kind: "learned_knowledge",
    title: "Learned: ticket themes ↔ renewals",
    summary: "Support latency tickets strengthen churn prediction.",
    at: "28m ago",
    entityIds: ["tkt-latency", "opp-renewal"],
    relationshipId: "rel-churn-risk",
    evidence: "prediction.score",
    lens: "learns",
  },
  {
    id: "ce-contradict",
    kind: "contradiction",
    title: "Contradiction: Roderick ↔ Gold Kist",
    summary: "Stale works_at conflicts with Acme association.",
    at: "2d ago",
    entityIds: ["con-roderick", "acct-gold"],
    relationshipId: "rel-gold-contradict",
    evidence: "stale_crm_row",
    lens: "learns",
  },
  {
    id: "ce-archived",
    kind: "archived_relationship",
    title: "Archived: Sarah ↔ Gold Kist mention",
    summary: "Weak co-mention archived — not confirmed knowledge.",
    at: "12d ago",
    entityIds: ["con-sarah", "acct-gold"],
    relationshipId: "rel-archived",
    evidence: "thread.co_occurrence",
    lens: "learns",
  },
  {
    id: "ce-fresh",
    kind: "freshness_change",
    title: "Freshness: Latency escalation",
    summary: "Ticket updated 40m ago — field highlight eligible.",
    at: "40m ago",
    entityIds: ["tkt-latency", "acct-acme"],
    relationshipId: "rel-ticket-acct",
    evidence: "support.ticket.updated_at",
    lens: "acts",
  },
  {
    id: "ce-predict",
    kind: "changed_relationship",
    title: "Predicted risk: Renewal ↔ Latency",
    summary: "Model raised risk_signal confidence.",
    at: "28m ago",
    entityIds: ["opp-renewal", "tkt-latency"],
    relationshipId: "rel-churn-risk",
    evidence: "prediction.score",
    lens: "predicts",
  },
]

export const HARNESS_PAGE_METRICS_RICH: HarnessPageContextMetrics = {
  knownEntities: HARNESS_ENTITIES.length,
  knownRelationships: HARNESS_RELATIONSHIPS.filter((r) => r.status !== "archived").length,
  note: "Mock populated graph — usable nodes = entities with ≥1 non-archived edge",
}

export const HARNESS_PAGE_METRICS_SPARSE: HarnessPageContextMetrics = {
  knownEntities: 0,
  knownRelationships: 32,
  note:
    "Prod bug class (fixed in code): relationship rows counted while entity ids omitted from SELECT. After deploy, counts must agree with query; 32 edges only become graph nodes if entity ids resolve.",
}

export const LENS_SPEC: Record<
  HarnessLens,
  {
    question: string
    entities: string
    relationships: string
    evidence: string
    defaultFocus: string
    selection: string
    inspector: string
    askContext: string
    empty: string
  }
> = {
  knows: {
    question: "What does Gravitre know about this business?",
    entities: "Accounts, contacts, opportunities, tickets, products with confirmed or learned links",
    relationships: "confirmed + learned (hide archived; dim contradictions)",
    evidence: "CRM FKs, email domain, deal associations",
    defaultFocus: "Highest-confidence account cluster",
    selection: "Entity → neighbors + why link exists + confidence",
    inspector: "Provenance, evidence chips, freshness, next actions",
    askContext: "Explain what we know about {entity} and its strongest relationships",
    empty: "No entities with resolvable ids — connect sources; do not invent nodes",
  },
  learns: {
    question: "What has Gravitre learned?",
    entities: "Entities touched by learned/contradicted/archived edges",
    relationships: "learned, contradicted, recently archived",
    evidence: "promotion / signature / stale-row evidence",
    defaultFocus: "Newest learned edge",
    selection: "Show learned vs confirmed distinction",
    inspector: "Learning status, confidence honesty, contradicting edges",
    askContext: "What did we learn about {entity} and how certain are we?",
    empty: "No learning events in window",
  },
  predicts: {
    question: "What is Gravitre predicting?",
    entities: "Entities on predicted / risk edges",
    relationships: "predicted risk_signal and model-linked edges",
    evidence: "prediction.score — never silent confidence theater",
    defaultFocus: "Highest predicted risk edge",
    selection: "Show model evidence + linked operational objects",
    inspector: "Prediction reason, confidence nullability, related ticket/opp",
    askContext: "Why is {entity} predicted at risk?",
    empty: "No predictions in window",
  },
  acts: {
    question: "What is Gravitre doing?",
    entities: "Entities on fresh / actionable operational paths",
    relationships: "confirmed edges tied to open tickets / active deals",
    evidence: "support + CRM freshness",
    defaultFocus: "Freshest operational entity",
    selection: "Surface investigate / open-in-source actions",
    inspector: "Actions available; link to Activity/Runs when real",
    askContext: "What should we do next regarding {entity}?",
    empty: "No actionable freshness in window",
  },
  improves: {
    question: "What has improved?",
    entities: "Entities on improved / product / confirmed outcome paths",
    relationships: "confirmed product and deal links with improvement evidence",
    evidence: "outcome / product associations",
    defaultFocus: "Opportunity + product cluster",
    selection: "Show before/after knowledge quality when available",
    inspector: "Improvement evidence; no invented ROI $",
    askContext: "What improved for {entity}?",
    empty: "No improvement signals in window",
  },
}

export const LENS_QUESTIONS: Record<HarnessLens, string> = {
  knows: LENS_SPEC.knows.question,
  learns: LENS_SPEC.learns.question,
  predicts: LENS_SPEC.predicts.question,
  acts: LENS_SPEC.acts.question,
  improves: LENS_SPEC.improves.question,
}

export function entitiesForLens(lens: HarnessLens) {
  return HARNESS_ENTITIES.map((e) => ({
    ...e,
    emphasized: e.lenses.includes(lens),
  }))
}

export function relationshipsForLens(lens: HarnessLens) {
  const isLearnsLens = lens === "learns"
  return HARNESS_RELATIONSHIPS.map((r) => {
    const inLens = r.lenses.includes(lens)
    const hideArchived = !isLearnsLens && r.status === "archived"
    return {
      ...r,
      emphasized: inLens && !hideArchived,
      visible: !hideArchived || isLearnsLens,
    }
  }).filter((r) => r.visible)
}

export function eventsForLens(lens: HarnessLens) {
  return HARNESS_CHANGE_EVENTS.filter((e) => e.lens === lens)
}

/** Usable graph nodes after count fix: entities that appear on ≥1 non-archived relationship */
export function usableEntityIdsFromRelationships(
  relationships = HARNESS_RELATIONSHIPS,
): Set<string> {
  const ids = new Set<string>()
  for (const r of relationships) {
    if (r.status === "archived") continue
    ids.add(r.fromId)
    ids.add(r.toId)
  }
  return ids
}

// ——— Activity harness compatibility ———

export const TRACE_STAGE_ORDER = [
  "intent",
  "plan",
  "agent",
  "tool",
  "action",
  "result",
  "verification",
  "outcome",
] as const

export const HARNESS_OUTCOMES: HarnessOutcome[] = [
  {
    id: "bo_01hq8s4m2k",
    title: "Created HubSpot contact for Jane Doe",
    status: "succeeded",
    runId: "run_01hq8s4m2k",
    createdAt: "1h ago",
    stages: [
      { id: "intent", label: "INTENT", status: "verified", summary: "Create contact", durationMs: 40 },
      { id: "plan", label: "PLAN", status: "verified", summary: "Use HubSpot write path", durationMs: 120 },
      { id: "agent", label: "AGENT", status: "verified", summary: "AE Router", actor: "AE Router", durationMs: 80 },
      { id: "tool", label: "TOOL", status: "verified", summary: "hubspot.contact.create", durationMs: 640 },
      { id: "action", label: "ACTION", status: "verified", summary: "Write contact", evidence: ["run outcome"], durationMs: 210 },
      { id: "result", label: "RESULT", status: "verified", summary: "Contact 40118 created", durationMs: 90 },
      { id: "verification", label: "VERIFICATION", status: "verified", summary: "Read-after-write matched", evidence: ["HubSpot re-read"], durationMs: 180 },
      { id: "outcome", label: "OUTCOME", status: "verified", summary: "Business outcome recorded", evidence: ["run outcome"] },
    ],
  },
]

/** Bridge: map entities → TopologyNode-compatible nodes for foundation scenes */
export const HARNESS_GRAPH_NODES: HarnessGraphNode[] = HARNESS_ENTITIES.map((e) => ({
  id: e.id,
  kind: e.kind,
  label: e.label,
  sublabel: e.sublabel,
  state: e.lenses.includes("acts") ? "active" : e.lenses.includes("learns") ? "learned" : "idle",
  x: e.x,
  y: e.y,
  lenses: e.lenses,
  provenance: e.sourceSystem,
}))

export const HARNESS_GRAPH_EDGES: HarnessGraphEdge[] = HARNESS_RELATIONSHIPS.filter(
  (r) => r.status !== "archived",
).map((r) => ({
  id: r.id,
  fromId: r.fromId,
  toId: r.toId,
  label: r.type,
  edgeType: r.type.toUpperCase(),
  state: r.status === "confirmed" ? "learned" : r.status === "predicted" ? "active" : "idle",
  lenses: r.lenses,
}))

export function nodesForLens(lens: HarnessLens) {
  return entitiesForLens(lens).map((e) => ({
    id: e.id,
    kind: e.kind,
    label: e.label,
    sublabel: e.sublabel,
    state: (e.emphasized ? "active" : "idle") as "idle" | "active",
    x: e.x,
    y: e.y,
    emphasized: e.emphasized,
  }))
}

export function edgesForLens(lens: HarnessLens) {
  return relationshipsForLens(lens).map((r) => ({
    id: r.id,
    fromId: r.fromId,
    toId: r.toId,
    label: r.type,
    state: (r.status === "predicted" ? "active" : r.status === "confirmed" ? "learned" : "idle") as
      | "idle"
      | "active"
      | "learned",
    emphasized: r.emphasized,
  }))
}
