"use client"

/**
 * UX/UI 3.0 Plus — I1 Field Topology + I2 Change Stream (harness only).
 * MOCK fixtures · KG-entity primary · one canonical graph · Cesar review gate.
 * Does NOT modify production /intelligence.
 */

import { useMemo, useState } from "react"
import Link from "next/link"
import { AnimatePresence, motion } from "framer-motion"
import { Button } from "@/components/ui/button"
import { EvidenceChip } from "@/components/gravitre/creative-grammar"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { useMotionPrefs } from "@/lib/animations"
import {
  HARNESS_CHANGE_EVENTS,
  HARNESS_ENTITIES,
  HARNESS_FIXTURE_LABEL,
  HARNESS_PAGE_METRICS_RICH,
  HARNESS_PAGE_METRICS_SPARSE,
  HARNESS_RELATIONSHIPS,
  LENS_SPEC,
  entitiesForLens,
  eventsForLens,
  relationshipsForLens,
  usableEntityIdsFromRelationships,
  type HarnessLens,
  type HarnessRelationship,
} from "./fixtures"
import { HarnessSurface, TopologyEdge, TopologyNode } from "./topology-primitives"
import { BeforeAfterPanel } from "./before-after-panel"

const LENSES: HarnessLens[] = ["knows", "learns", "predicts", "acts", "improves"]

function confidenceLabel(c: number | null) {
  if (c == null) return "confidence unknown"
  return `${Math.round(c * 100)}% confidence`
}

function statusTone(status: HarnessRelationship["status"]): "evidence" | "waiting" | "error" {
  if (status === "contradicted") return "error"
  if (status === "predicted") return "waiting"
  return "evidence"
}

function CurrentProductionStub() {
  return (
    <div
      className="rounded-xl border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-4"
      data-testid="intel-current-stub"
    >
      <p className={TYPE.eyebrow}>CURRENT PRODUCTION · /intelligence</p>
      <p className={cn(TYPE.cardTitle, "mt-2")}>IntelligenceGraphStage living map</p>
      <ul className={cn(TYPE.bodyMuted, "mt-3 list-disc space-y-1 pl-5 text-sm")}>
        <li>Hub-centric diagram editor feel; sparse canvas</li>
        <li>CoreStats: knowledge metrics separate from rendered MapNodes</li>
        <li>0 entities · 32 relationships = SELECT omitted entity ids (fixed in KG service)</li>
        <li>Lenses project departments/agents/signals — not KG entity topology</li>
        <li>CES KF-A / TRACE grammar did not replace this surface</li>
      </ul>
      <div className="mt-4 flex h-[200px] flex-col items-center justify-center rounded-lg border border-dashed border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)]">
        <div className="h-12 w-12 rounded-full bg-[color:var(--g-intelligence-soft)] ring-2 ring-[color:var(--g-intelligence)]" />
        <p className={cn(TYPE.meta, "mt-3")}>Gravitre Intelligence</p>
        <p className="text-xs font-medium text-[color:var(--g-text-secondary)]">0 entities · 32 relationships</p>
      </div>
      <p className={cn(TYPE.meta, "mt-3")}>
        DATA CONTRACT: IntelligencePageContextResponse.graph + org_entity_relationships —
        presentation must not invent a second fabric.
      </p>
    </div>
  )
}

export function IntelligenceFieldPrototype({ scene }: { scene: string }) {
  const { reduced } = useMotionPrefs()
  const forceReduced = scene.includes("reduced") || reduced
  const isMobile = scene.includes("mobile")
  const isLoading = scene.includes("loading")
  const isEmpty = scene.includes("empty")
  const isError = scene.includes("error")
  const isCompare = scene.includes("compare")
  const sparseMetrics = scene.includes("sparse")
  const isLarge = scene.includes("large")
  const showInspector = !scene.includes("empty") && !scene.includes("error") && !scene.includes("loading")
  const [lens, setLens] = useState<HarnessLens>(
    scene.includes("lens") ? "predicts" : "knows",
  )
  const [streamOpen, setStreamOpen] = useState(
    scene.includes("change") || scene.includes("compare") || scene.includes("default") || scene.includes("selected"),
  )
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(
    scene.includes("selected") || scene.includes("ai") || scene.includes("default") || scene.includes("compare")
      ? "acct-acme"
      : scene.includes("change")
        ? "con-roderick"
        : null,
  )
  const [selectedRelId, setSelectedRelId] = useState<string | null>(
    scene.includes("relationship") || scene.includes("change") ? "rel-works-roderick" : null,
  )
  const [selectedEventId, setSelectedEventId] = useState<string | null>(
    scene.includes("change") ? "ce-changed" : null,
  )

  const metrics = sparseMetrics ? HARNESS_PAGE_METRICS_SPARSE : HARNESS_PAGE_METRICS_RICH
  const spec = LENS_SPEC[lens]
  const entities = useMemo(() => entitiesForLens(lens), [lens])
  const relationships = useMemo(() => relationshipsForLens(lens), [lens])
  const events = useMemo(() => eventsForLens(lens), [lens])
  const usableIds = useMemo(() => usableEntityIdsFromRelationships(), [])

  const focusIds = useMemo(() => {
    if (selectedEventId) {
      const ev = HARNESS_CHANGE_EVENTS.find((e) => e.id === selectedEventId)
      return ev?.entityIds ?? []
    }
    if (selectedRelId) {
      const rel = HARNESS_RELATIONSHIPS.find((r) => r.id === selectedRelId)
      return rel ? [rel.fromId, rel.toId] : []
    }
    if (selectedEntityId) return [selectedEntityId]
    return []
  }, [selectedEventId, selectedRelId, selectedEntityId])

  const selectedEntity = HARNESS_ENTITIES.find((e) => e.id === selectedEntityId)
  const selectedRel = HARNESS_RELATIONSHIPS.find((r) => r.id === selectedRelId)
  const selectedEvent = HARNESS_CHANGE_EVENTS.find((e) => e.id === selectedEventId)

  const scale = isLarge ? 1 : 1
  const vb = isLarge ? "0 0 800 440" : "0 0 800 440"

  const field = (
    <div className={cn("flex flex-col", isMobile ? "max-w-[390px]" : "min-h-[620px]")} data-testid="intel-i1-i2">
      <div className="flex items-center justify-between gap-3 border-b border-[color:var(--g-border-subtle)] pb-3">
        <div className="flex min-w-0 items-center gap-2">
          <NucleoIntelligence size={20} />
          <h2 className={TYPE.pageTitle}>Intelligence</h2>
        </div>
        <Button type="button" size="sm" variant={streamOpen ? "secondary" : "outline"} onClick={() => setStreamOpen((v) => !v)}>
          {streamOpen ? "Hide changes" : "What changed?"}
        </Button>
      </div>

      <div className="mt-3 flex gap-1 overflow-x-auto pb-1" role="tablist" aria-label="Intelligence lenses">
        {LENSES.map((id) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={lens === id}
            onClick={() => {
              setLens(id)
              setSelectedEventId(null)
            }}
            className={cn(
              "shrink-0 rounded-md px-3 py-1.5 text-xs font-semibold capitalize",
              lens === id
                ? "bg-[color:var(--g-intelligence-soft)] text-[color:var(--g-intelligence)]"
                : "text-[color:var(--g-text-muted)] hover:bg-[color:var(--g-surface-2)]",
            )}
          >
            {id}
          </button>
        ))}
      </div>

      <p className={cn(TYPE.meta, "mt-2")}>{spec.question}</p>
      <p className={cn(TYPE.meta, "mt-0.5")}>
        {HARNESS_FIXTURE_LABEL} · {metrics.knownEntities} entities · {metrics.knownRelationships} relationships
        {!sparseMetrics ? ` · ${usableIds.size} usable nodes` : ""}
      </p>

      <div className={cn("relative mt-4 flex flex-1 gap-0", isMobile && "flex-col")}>
        <AnimatePresence>
          {streamOpen && !isEmpty && !isError && !isLoading ? (
            <motion.aside
              initial={forceReduced ? false : { width: 0, opacity: 0 }}
              animate={{ width: isMobile ? "100%" : 260, opacity: 1 }}
              exit={forceReduced ? undefined : { width: 0, opacity: 0 }}
              className={cn(
                "shrink-0 overflow-hidden border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)]",
                isMobile ? "mb-3 rounded-lg border p-2" : "border-r",
              )}
              data-testid="intel-i2-stream"
            >
              <p className={cn(TYPE.eyebrow, "px-3 pt-3")}>Change stream · I2</p>
              <p className={cn(TYPE.meta, "px-3 pb-1")}>Real event kinds · filtered by {lens}</p>
              <ul className="max-h-[460px] overflow-y-auto px-2 pb-2">
                {events.length === 0 ? (
                  <li className={cn(TYPE.meta, "px-2 py-3")}>{spec.empty}</li>
                ) : (
                  events.map((ev) => (
                    <li key={ev.id}>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedEventId(ev.id)
                          setSelectedRelId(ev.relationshipId ?? null)
                          setSelectedEntityId(ev.entityIds[0] ?? null)
                        }}
                        className={cn(
                          "w-full rounded-md px-2 py-2 text-left hover:bg-[color:var(--g-surface-2)]",
                          selectedEventId === ev.id && "bg-[color:var(--g-surface-2)]",
                        )}
                      >
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-[color:var(--g-text-muted)]">
                          {ev.kind.replace(/_/g, " ")}
                        </p>
                        <p className="text-xs font-semibold text-[color:var(--g-text-primary)]">{ev.title}</p>
                        <p className={cn(TYPE.meta, "mt-0.5")}>{ev.at}</p>
                      </button>
                    </li>
                  ))
                )}
              </ul>
            </motion.aside>
          ) : null}
        </AnimatePresence>

        <HarnessSurface className={cn("relative min-h-[440px] flex-1 overflow-hidden", isMobile && "min-h-[340px]")} data-testid="intel-i1-field">
          {isLoading ? (
            <div className="flex h-full min-h-[420px] items-center justify-center p-6">
              <p className={TYPE.bodyMuted}>Loading intelligence field…</p>
            </div>
          ) : null}
          {isError ? (
            <div className="flex h-full min-h-[420px] flex-col items-center justify-center gap-3 p-6 text-center">
              <p className={TYPE.sectionTitle}>Unable to load intelligence</p>
              <p className={cn(TYPE.bodyMuted, "max-w-sm")}>
                Page-context failed. Retry the same org-scoped contract — no invented graph.
              </p>
              <Button type="button" size="sm" variant="outline">Retry</Button>
            </div>
          ) : null}
          {isEmpty || (sparseMetrics && metrics.knownEntities === 0) ? (
            <div className="flex h-full min-h-[420px] flex-col items-center justify-center p-6 text-center" data-testid="intel-empty">
              <p className={TYPE.sectionTitle}>
                {isEmpty ? "No knowledge graph yet" : "No displayable entities"}
              </p>
              <p className={cn(TYPE.bodyMuted, "mt-2 max-w-md")}>
                {isEmpty
                  ? "Connect sources and sync CRM so org_entity_relationships can resolve entity ids."
                  : `${metrics.knownRelationships} relationship rows exist without resolvable entity ids. Do not invent nodes. After the SELECT fix deploys, recount; only edges with both endpoint ids become usable nodes.`}
              </p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                <Button type="button" size="sm" asChild>
                  <Link href="/connectors">Open connectors</Link>
                </Button>
                <Button type="button" size="sm" variant="outline" asChild>
                  <Link href="/docs">Docs</Link>
                </Button>
              </div>
              <p className={cn(TYPE.meta, "mt-4 max-w-sm")}>{metrics.note}</p>
            </div>
          ) : null}
          {!isLoading && !isError && !isEmpty && !(sparseMetrics && metrics.knownEntities === 0) ? (
            <svg viewBox={vb} className="h-full min-h-[420px] w-full" role="img" aria-label="Knowledge field topology" style={{ transform: `scale(${scale})` }}>
              {relationships.map((rel) => {
                const from = HARNESS_ENTITIES.find((e) => e.id === rel.fromId)!
                const to = HARNESS_ENTITIES.find((e) => e.id === rel.toId)!
                const selected = selectedRelId === rel.id
                const highlighted =
                  selected ||
                  focusIds.includes(rel.fromId) ||
                  focusIds.includes(rel.toId)
                return (
                  <g
                    key={rel.id}
                    role="button"
                    tabIndex={0}
                    className="cursor-pointer"
                    onClick={() => {
                      setSelectedRelId(rel.id)
                      setSelectedEntityId(null)
                      setSelectedEventId(null)
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        setSelectedRelId(rel.id)
                        setSelectedEntityId(null)
                      }
                    }}
                    data-testid={`intel-rel-${rel.id}`}
                  >
                    <TopologyEdge
                      x1={from.x}
                      y1={from.y}
                      x2={to.x}
                      y2={to.y}
                      label={rel.emphasized || selected ? rel.type : undefined}
                      state={
                        rel.status === "predicted"
                          ? "active"
                          : rel.status === "confirmed" || rel.status === "learned"
                            ? "learned"
                            : "idle"
                      }
                      active={highlighted}
                      learned={rel.status === "confirmed"}
                      reducedMotion={forceReduced}
                      opacity={rel.emphasized || highlighted ? 1 : 0.18}
                    />
                  </g>
                )
              })}
              {entities.map((ent) => (
                <g key={ent.id} opacity={ent.emphasized || focusIds.includes(ent.id) ? 1 : 0.25}>
                  <TopologyNode
                    x={ent.x}
                    y={ent.y}
                    label={ent.label}
                    sublabel={ent.sublabel}
                    kind={ent.kind}
                    state={
                      ent.emphasized
                        ? lens === "predicts"
                          ? "warning"
                          : lens === "acts"
                            ? "active"
                            : "learned"
                        : "idle"
                    }
                    selected={focusIds.includes(ent.id) || selectedEntityId === ent.id}
                    reducedMotion={forceReduced}
                    onClick={() => {
                      setSelectedEntityId(ent.id)
                      setSelectedRelId(null)
                      setSelectedEventId(null)
                    }}
                  />
                </g>
              ))}
            </svg>
          ) : null}
        </HarnessSurface>

        <AnimatePresence>
          {showInspector && (selectedEntity || selectedRel) && !isEmpty && !isError && !isLoading ? (
            <motion.aside
              initial={forceReduced ? false : { x: 20, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={forceReduced ? undefined : { x: 20, opacity: 0 }}
              className={cn(
                "shrink-0 border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)]",
                isMobile ? "mt-3 w-full rounded-xl border p-4" : "w-[300px] border-l p-4",
              )}
              data-testid="intel-inspector"
            >
              {selectedRel ? (
                <>
                  <p className={TYPE.eyebrow}>Relationship</p>
                  <p className={cn(TYPE.cardTitle, "mt-2")}>{selectedRel.type}</p>
                  <p className={cn(TYPE.meta, "mt-1")}>
                    {HARNESS_ENTITIES.find((e) => e.id === selectedRel.fromId)?.label} →{" "}
                    {HARNESS_ENTITIES.find((e) => e.id === selectedRel.toId)?.label}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    <EvidenceChip label={selectedRel.status} tone={statusTone(selectedRel.status)} />
                    <EvidenceChip label={confidenceLabel(selectedRel.confidence)} tone="evidence" />
                  </div>
                  <p className={cn(TYPE.bodyMuted, "mt-3 text-sm")}>{selectedRel.reason}</p>
                  <div className="mt-3 space-y-1">
                    {selectedRel.evidence.map((ev) => (
                      <EvidenceChip key={ev} label={ev} tone="evidence" />
                    ))}
                  </div>
                </>
              ) : selectedEntity ? (
                <>
                  <p className={TYPE.eyebrow}>Entity</p>
                  <p className={cn(TYPE.cardTitle, "mt-2")}>{selectedEntity.label}</p>
                  <p className={cn(TYPE.meta, "mt-1")}>
                    {selectedEntity.kind} · {selectedEntity.sourceSystem} · fresh {selectedEntity.freshness}
                  </p>
                  <p className={cn(TYPE.bodyMuted, "mt-3 text-sm")}>{spec.inspector}</p>
                  <div className="mt-3 space-y-1">
                    {HARNESS_RELATIONSHIPS.filter(
                      (r) =>
                        (r.fromId === selectedEntity.id || r.toId === selectedEntity.id) &&
                        r.status !== "archived",
                    )
                      .slice(0, 4)
                      .map((r) => (
                        <button
                          key={r.id}
                          type="button"
                          className="block w-full rounded-md border border-[color:var(--g-border-subtle)] px-2 py-1.5 text-left text-xs hover:border-[color:var(--color-brand,#16a374)]"
                          onClick={() => setSelectedRelId(r.id)}
                        >
                          {r.type} · {confidenceLabel(r.confidence)}
                        </button>
                      ))}
                  </div>
                </>
              ) : null}

              {selectedEvent ? (
                <div className="mt-3 rounded-md border border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)] p-2">
                  <p className={TYPE.eyebrow}>From change stream</p>
                  <p className="mt-1 text-xs font-medium">{selectedEvent.title}</p>
                </div>
              ) : null}

              <div className="mt-4 space-y-2">
                <p className={TYPE.eyebrow}>Actions</p>
                <Button type="button" size="sm" variant="outline" className="w-full" disabled>
                  Open in source (when linked)
                </Button>
              </div>
              <div className="mt-4 rounded-lg border border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)] p-3">
                <p className={TYPE.eyebrow}>Ask · canonical workspace</p>
                <p className={cn(TYPE.bodyMuted, "mt-1 text-sm")}>
                  {spec.askContext.replace(
                    "{entity}",
                    selectedEntity?.label ?? selectedRel?.type ?? "selection",
                  )}
                </p>
                <Button type="button" size="sm" className="mt-2 w-full">
                  Ask about selection
                </Button>
                <p className={cn(TYPE.meta, "mt-2")}>Summons AI Workspace — not a second chat runtime.</p>
              </div>
            </motion.aside>
          ) : null}
        </AnimatePresence>
      </div>
    </div>
  )

  return (
    <div data-review-surface="intelligence" data-review-scene={scene} data-testid="intelligence-field-prototype">
      {isCompare ? (
        <div className="space-y-6">
          <div>
            <p className={TYPE.eyebrow}>3.0 Plus · Intelligence design review</p>
            <h2 className={cn(TYPE.pageTitle, "mt-1")}>CURRENT vs PROPOSED I1/I2 vs DATA CONTRACT</h2>
            <p className={cn(TYPE.pageLead, "mt-2")}>
              Production route unchanged. Fixtures labeled MOCK. Cesar gate before any swap.
            </p>
          </div>
          <div className="grid gap-6 xl:grid-cols-2">
            <CurrentProductionStub />
            <div>
              <p className={TYPE.eyebrow}>PROPOSED · I1 entity field + I2 event stream</p>
              <div className="mt-2">{field}</div>
            </div>
          </div>
          <HarnessSurface className="p-4" elevated>
            <p className={TYPE.eyebrow}>ACTUAL KNOWLEDGE-GRAPH DATA CONTRACT</p>
            <ul className={cn(TYPE.bodyMuted, "mt-2 list-disc space-y-1 pl-5 text-sm")}>
              <li>GET /api/intelligence/page-context → IntelligencePageContextResponse</li>
              <li>graph.nodes / graph.edges from intelligence_graph_builder (lens filter on one graph)</li>
              <li>Metrics knownEntities / knownRelationships from get_admin_summary(org_id)</li>
              <li>org_entity_relationships: source/target entity ids + types + confidence + evidence</li>
              <li>Harness MOCK mirrors these shapes — does not write to org graph</li>
            </ul>
          </HarnessSurface>
        </div>
      ) : (
        field
      )}

      <BeforeAfterPanel
        surface="intelligence"
        changes={[
          { action: "removed", detail: "Department/agent/signal décor as substitute for KG entities" },
          { action: "removed", detail: "Cosmetic lens color toggles without content change" },
          { action: "consolidated", detail: "One canonical entity/relationship set; lenses emphasize subsets" },
          { action: "clearer", detail: "I2 events: new/changed/confirmed/learned/contradiction/archived/freshness" },
          { action: "honest", detail: "Confidence nullability + sparse entity empty state" },
          { action: "visual", detail: "Select entity OR relationship → inspector + Ask context" },
        ]}
      />
    </div>
  )
}
