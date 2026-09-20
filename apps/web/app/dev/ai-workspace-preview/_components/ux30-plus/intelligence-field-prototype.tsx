"use client"

import { useMemo, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { Button } from "@/components/ui/button"
import { EvidenceChip } from "@/components/gravitre/creative-grammar"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { useMotionPrefs } from "@/lib/animations"
import {
  HARNESS_CHANGE_EVENTS,
  HARNESS_FIXTURE_LABEL,
  HARNESS_GRAPH_EDGES,
  HARNESS_GRAPH_NODES,
  type HarnessLens,
} from "./fixtures"
import { HarnessSurface, TopologyEdge, TopologyNode } from "./topology-primitives"
import { BeforeAfterPanel } from "./before-after-panel"

const LENSES: { id: HarnessLens; label: string }[] = [
  { id: "knows", label: "Knows" },
  { id: "learns", label: "Learns" },
  { id: "predicts", label: "Predicts" },
  { id: "acts", label: "Acts" },
  { id: "improves", label: "Improves" },
]

export function IntelligenceFieldPrototype({ scene }: { scene: string }) {
  const { reduced } = useMotionPrefs()
  const forceReduced = scene.includes("reduced") || reduced
  const isMobile = scene.includes("mobile")
  const isLoading = scene.includes("loading")
  const isEmpty = scene.includes("empty")
  const isError = scene.includes("error")
  const showInspector = scene.includes("inspector") || scene.includes("selected") || scene.includes("ai")
  const showAi = scene.includes("ai")
  const [lens, setLens] = useState<HarnessLens>("knows")
  const [streamOpen, setStreamOpen] = useState(
    scene.includes("default") ? false : !scene.includes("empty"),
  )
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(
    showInspector ? "hubspot" : null,
  )
  const [selectedEventId, setSelectedEventId] = useState<string | null>(
    showInspector ? "ce3" : null,
  )

  const focusIds = useMemo(() => {
    if (selectedEventId) {
      return HARNESS_CHANGE_EVENTS.find((e) => e.id === selectedEventId)?.entityIds ?? []
    }
    if (selectedNodeId) return [selectedNodeId]
    return []
  }, [selectedEventId, selectedNodeId])

  const selectedNode = HARNESS_GRAPH_NODES.find((n) => n.id === selectedNodeId)
  const selectedEvent = HARNESS_CHANGE_EVENTS.find((e) => e.id === selectedEventId)

  return (
    <div data-review-surface="intelligence" data-review-scene={scene}>
      <div className={cn("flex flex-col", isMobile ? "max-w-[390px]" : "min-h-[640px]")}>
        {/* Header — no description block */}
        <div className="flex items-center justify-between gap-3 border-b border-[color:var(--g-border-subtle)] pb-3">
          <div className="flex items-center gap-2">
            <NucleoIntelligence size={20} />
            <h2 className={TYPE.pageTitle}>Intelligence</h2>
          </div>
          <Button
            type="button"
            size="sm"
            variant={streamOpen ? "secondary" : "outline"}
            onClick={() => setStreamOpen((v) => !v)}
          >
            {streamOpen ? "Hide changes" : "What changed?"}
          </Button>
        </div>

        {/* Lens bar */}
        <div className="mt-3 flex gap-1 overflow-x-auto pb-1">
          {LENSES.map((l) => (
            <button
              key={l.id}
              type="button"
              onClick={() => setLens(l.id)}
              className={cn(
                "shrink-0 rounded-full px-3 py-1 text-xs font-medium transition-colors",
                lens === l.id
                  ? "bg-[color:var(--g-intelligence-soft)] text-[color:var(--g-intelligence)]"
                  : "text-[color:var(--g-text-muted)] hover:bg-[color:var(--g-surface-2)]",
              )}
            >
              {l.label}
            </button>
          ))}
        </div>

        <p className={cn(TYPE.meta, "mt-1")}>{HARNESS_FIXTURE_LABEL}</p>

        <div className={cn("relative mt-4 flex flex-1 gap-0", isMobile && "flex-col")}>
          {/* I2 — contextual change stream (collapsible, not 50/50 split) */}
          <AnimatePresence>
            {streamOpen && !isEmpty ? (
              <motion.aside
                initial={forceReduced ? false : { width: 0, opacity: 0 }}
                animate={{ width: isMobile ? "100%" : 240, opacity: 1 }}
                exit={forceReduced ? undefined : { width: 0, opacity: 0 }}
                transition={forceReduced ? { duration: 0 } : { type: "spring", stiffness: 280, damping: 28 }}
                className={cn(
                  "shrink-0 overflow-hidden border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)]",
                  isMobile ? "mb-3 rounded-lg border p-2" : "border-r",
                )}
              >
                <p className={cn(TYPE.eyebrow, "px-3 pt-3")}>Change stream</p>
                <ul className="max-h-[420px] overflow-y-auto px-2 pb-2">
                  {HARNESS_CHANGE_EVENTS.map((ev) => (
                    <li key={ev.id}>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedEventId(ev.id)
                          setSelectedNodeId(null)
                        }}
                        className={cn(
                          "w-full rounded-lg px-2 py-2.5 text-left transition-colors",
                          selectedEventId === ev.id && "bg-[color:var(--g-surface-active)]",
                        )}
                      >
                        <p className="text-xs font-medium text-[color:var(--g-text-primary)]">{ev.title}</p>
                        <p className={cn(TYPE.meta, "mt-0.5 line-clamp-2")}>{ev.summary}</p>
                        <p className={cn(TYPE.meta, "mt-1")}>{ev.at}</p>
                      </button>
                    </li>
                  ))}
                </ul>
              </motion.aside>
            ) : null}
          </AnimatePresence>

          {/* I1 — field topology (primary) */}
          <HarnessSurface className="relative min-h-[420px] flex-1 overflow-hidden">
            {isLoading ? (
              <div className="absolute inset-0 animate-pulse bg-[color:var(--g-surface-2)]/40" />
            ) : null}
            {isError ? (
              <div className="flex h-full flex-col items-center justify-center p-6 text-center">
                <p className="text-sm font-medium text-[color:var(--g-danger)]">Could not load intelligence snapshot</p>
                <Button type="button" size="sm" variant="outline" className="mt-3">
                  Retry
                </Button>
              </div>
            ) : null}
            {isEmpty ? (
              <div className="flex h-full flex-col items-center justify-center p-6 text-center">
                <p className={TYPE.sectionTitle}>No graph yet</p>
                <p className={cn(TYPE.bodyMuted, "mt-2 max-w-sm")}>
                  Connect sources and run workflows to populate the intelligence field.
                </p>
              </div>
            ) : null}
            {!isLoading && !isError && !isEmpty ? (
              <svg viewBox="0 0 800 440" className="h-full min-h-[420px] w-full">
                {HARNESS_GRAPH_EDGES.map((edge) => {
                  const from = HARNESS_GRAPH_NODES.find((n) => n.id === edge.fromId)!
                  const to = HARNESS_GRAPH_NODES.find((n) => n.id === edge.toId)!
                  const highlighted =
                    focusIds.includes(edge.fromId) || focusIds.includes(edge.toId)
                  return (
                    <TopologyEdge
                      key={edge.id}
                      x1={from.x}
                      y1={from.y}
                      x2={to.x}
                      y2={to.y}
                      label={edge.label}
                      state={edge.state}
                      active={highlighted}
                      learned={edge.state === "learned"}
                      reducedMotion={forceReduced}
                    />
                  )
                })}
                {HARNESS_GRAPH_NODES.map((node) => (
                  <TopologyNode
                    key={node.id}
                    x={node.x}
                    y={node.y}
                    label={node.label}
                    sublabel={node.sublabel}
                    kind={node.kind}
                    state={node.state}
                    selected={focusIds.includes(node.id) || selectedNodeId === node.id}
                    reducedMotion={forceReduced}
                    onClick={() => {
                      setSelectedNodeId(node.id)
                      setSelectedEventId(null)
                    }}
                  />
                ))}
              </svg>
            ) : null}
          </HarnessSurface>

          {/* Inspector */}
          <AnimatePresence>
            {showInspector && selectedNode && !isEmpty ? (
              <motion.aside
                initial={forceReduced ? false : { x: 24, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={forceReduced ? undefined : { x: 24, opacity: 0 }}
                className={cn(
                  "shrink-0 border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)]",
                  isMobile ? "mt-3 w-full rounded-xl border p-4" : "w-[320px] border-l p-4",
                )}
              >
                <p className={TYPE.eyebrow}>Inspector</p>
                <p className={cn(TYPE.cardTitle, "mt-2")}>{selectedNode.label}</p>
                <p className={cn(TYPE.meta, "mt-1")}>{selectedNode.kind}</p>
                {selectedEvent?.evidence ? (
                  <div className="mt-3">
                    <EvidenceChip label={selectedEvent.evidence} tone="evidence" />
                  </div>
                ) : null}
                {showAi ? (
                  <div className="mt-4 rounded-lg border border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)] p-3">
                    <p className={TYPE.eyebrow}>Ask about this</p>
                    <p className={cn(TYPE.bodyMuted, "mt-1 text-sm")}>
                      Context: {selectedNode.label} · lens {lens}
                    </p>
                    <Button type="button" size="sm" className="mt-2 w-full">
                      Explain connection
                    </Button>
                  </div>
                ) : null}
              </motion.aside>
            ) : null}
          </AnimatePresence>
        </div>
      </div>

      <BeforeAfterPanel
        surface="intelligence"
        changes={[
          { action: "removed", detail: "Five-column bordered evidence box below map" },
          { action: "removed", detail: "Page description block under title" },
          { action: "consolidated", detail: "Lens + field + inspector into one primary canvas" },
          { action: "contextual", detail: "Change stream (I2) opens on demand — field stays primary" },
          { action: "visual", detail: "Shared topology node/edge geometry with Activity trace" },
          { action: "clearer", detail: "Selecting change event focuses topology + evidence chip" },
        ]}
      />
    </div>
  )
}
