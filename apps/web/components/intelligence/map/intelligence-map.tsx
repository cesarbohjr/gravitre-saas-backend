"use client"

/**
 * Map-first Intelligence surface — Phase B: each lens renders a distinct topology
 * from real endpoints (departments, agents, knowledge types, models, signals).
 */

import { useEffect, useMemo, useState } from "react"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import type { IntelligenceCoreDepartment, IntelligenceCoreStateResponse } from "@/lib/api"
import type { Agent } from "@/types/api"
import { useIntelligenceCoreState } from "@/lib/intelligence/use-core-state"
import { CoreHubNode } from "@/components/intelligence/core/core-hub-node"
import { DepartmentNode } from "@/components/intelligence/core/department-node"
import { SignalEdge } from "@/components/intelligence/core/signal-edge"
import type { IntelligenceMapLens } from "./intelligence-map-lens"
import {
  buildMapTopology,
  CORE_ID,
  layoutMapNodes,
  signalDepartmentKey,
  type MapNode,
} from "./map-topology"
import { MapSatelliteNode } from "./map-satellite-node"
import { TYPE } from "@/lib/design-system"
import { readString } from "@/lib/intelligence/helpers"
import { cn } from "@/lib/utils"
import { Warning } from "@phosphor-icons/react"

const VB = { w: 1000, h: 520 }
const CENTER = { cx: VB.w / 2, cy: VB.h / 2 }

type BusinessSignalRow = Record<string, unknown>

export type IntelligenceMapSelection =
  | { kind: "department"; department: IntelligenceCoreDepartment }
  | { kind: "agent"; agent: Agent }
  | { kind: "signal"; signal: BusinessSignalRow }
  | { kind: "satellite"; node: MapNode }
  | null

function CoreStats({
  data,
  lens,
  entityCount,
  relationshipCount,
  caption,
}: {
  data: IntelligenceCoreStateResponse
  lens: IntelligenceMapLens
  entityCount?: number | null
  relationshipCount?: number | null
  caption: string
}) {
  const lines: string[] = []
  if (lens === "knows") {
    if (entityCount != null) lines.push(`${entityCount.toLocaleString()} entities`)
    if (relationshipCount != null) lines.push(`${relationshipCount.toLocaleString()} relationships`)
  } else if (lens === "acts") {
    if (data.core.activeAgentRuns > 0) {
      lines.push(`${data.core.activeAgentRuns} agent run${data.core.activeAgentRuns === 1 ? "" : "s"}`)
    }
    if (data.core.pendingApprovalsTotal > 0) {
      lines.push(`${data.core.pendingApprovalsTotal} pending approval${data.core.pendingApprovalsTotal === 1 ? "" : "s"}`)
    }
  } else if (lens === "improves") {
    const resolved = data.departments.reduce((sum, d) => sum + d.recentResolved, 0)
    if (resolved > 0) lines.push(`${resolved} resolved in window`)
  }

  return (
    <div className="pointer-events-none absolute left-1/2 top-[calc(50%+4.75rem)] z-20 max-w-md -translate-x-1/2 px-4 text-center">
      <p className={cn(TYPE.meta, "whitespace-nowrap text-[color:var(--g-text-muted)]")}>
        Gravitre Intelligence
      </p>
      <p className="mt-0.5 text-xs font-medium text-[color:var(--g-text-secondary)]">
        {lines.length > 0 ? lines.join(" · ") : caption}
      </p>
    </div>
  )
}

function selectionKey(selection: IntelligenceMapSelection): string | null {
  if (!selection) return null
  if (selection.kind === "department") return `dept:${selection.department.id}`
  if (selection.kind === "agent") return `agent:${selection.agent.id}`
  if (selection.kind === "signal") {
    return `signal:${readString(selection.signal.id, readString(selection.signal.title, ""))}`
  }
  return selection.node.id
}

export function IntelligenceMap({
  lens,
  signals,
  agents,
  entityTypes,
  readiness,
  orgTraining,
  entityCount,
  relationshipCount,
  selection,
  onSelectionChange,
  className,
}: {
  lens: IntelligenceMapLens
  signals?: BusinessSignalRow[] | null
  agents?: Agent[] | null
  entityTypes?: string[] | null
  readiness?: Record<string, unknown> | null
  orgTraining?: Record<string, { artifact_loaded?: boolean }> | null
  entityCount?: number | null
  relationshipCount?: number | null
  selection?: IntelligenceMapSelection
  onSelectionChange?: (selection: IntelligenceMapSelection) => void
  className?: string
}) {
  const reducePreference = useReducedMotion()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  const reduced = mounted && !!reducePreference

  const { data, error, isLoading } = useIntelligenceCoreState(true, 24)

  const topology = useMemo(() => {
    if (!data) {
      return { nodes: [], edges: [], caption: "" }
    }
    return buildMapTopology({
      lens,
      departments: data.departments,
      agents,
      entityTypes,
      readiness,
      orgTraining,
      signals,
      coreState: data.core.state,
    })
  }, [lens, data, agents, entityTypes, readiness, orgTraining, signals])

  const positions = useMemo(
    () => layoutMapNodes(topology.nodes, CENTER, lens),
    [topology.nodes, lens],
  )

  const posById = useMemo(() => {
    const map = new Map<string, { x: number; y: number }>()
    map.set(CORE_ID, { x: CENTER.cx, y: CENTER.cy })
    positions.forEach((pos, id) => map.set(id, pos))
    return map
  }, [positions])

  const warningsByDept = useMemo(() => {
    const map = new Map<string, BusinessSignalRow>()
    for (const signal of signals ?? []) {
      const key = signalDepartmentKey(signal)
      if (key && !map.has(key)) map.set(key, signal)
    }
    return map
  }, [signals])

  const selectedId = selectionKey(selection ?? null)
  const hasAnyRealSignal =
    topology.nodes.length > 0 ||
    (data?.core.pendingApprovalsTotal ?? 0) > 0 ||
    (data?.core.activeAgentRuns ?? 0) > 0

  const toggleSelection = (node: MapNode) => {
    const isSelected = selectedId === node.id
    if (isSelected) {
      onSelectionChange?.(null)
      return
    }
    if (node.kind === "department" && node.department) {
      onSelectionChange?.({ kind: "department", department: node.department })
      return
    }
    if (node.kind === "agent" && node.agent) {
      onSelectionChange?.({ kind: "agent", agent: node.agent })
      return
    }
    if (node.kind === "signal" && node.signal) {
      onSelectionChange?.({ kind: "signal", signal: node.signal })
      return
    }
    onSelectionChange?.({ kind: "satellite", node })
  }

  return (
    <div
      id="intelligence-map-canvas"
      className={cn(
        "relative min-h-[44vh] flex-1 overflow-hidden rounded-[var(--np-radius-lg)] border border-[color:var(--g-brand-border)]/30 bg-gradient-to-b from-[color:var(--g-intelligence-surface)]/40 via-[color:var(--g-surface-1)] to-[color:var(--g-surface-2)] shadow-[var(--np-shadow)]",
        className,
      )}
      role="img"
      aria-label={`Interactive Gravitre intelligence map — ${lens} lens`}
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.35]"
        aria-hidden
        style={{
          backgroundImage:
            "radial-gradient(circle at 50% 45%, color-mix(in oklch, var(--g-intelligence) 12%, transparent) 0%, transparent 55%), linear-gradient(var(--color-line,#eaedf1) 1px, transparent 1px), linear-gradient(90deg, var(--color-line,#eaedf1) 1px, transparent 1px)",
          backgroundSize: "100% 100%, 48px 48px, 48px 48px",
        }}
      />

      <p className={cn(TYPE.meta, "absolute left-3 top-2 z-20 max-w-[70%] truncate opacity-80")}>
        {topology.caption}
      </p>

      {error ? (
        <div className="relative z-10 flex h-full min-h-[44vh] items-center justify-center p-6 text-center">
          <div>
            <p className={TYPE.cardTitle}>Unable to load live intelligence map</p>
            <p className={cn(TYPE.meta, "mt-1")}>Try refreshing the page in a moment.</p>
          </div>
        </div>
      ) : isLoading && !data ? (
        <div className="relative z-10 flex h-full min-h-[44vh] items-center justify-center">
          <span className={TYPE.bodyMuted}>Loading live intelligence topology…</span>
        </div>
      ) : topology.nodes.length === 0 && !hasAnyRealSignal ? (
        <div className="relative z-10 flex h-full min-h-[44vh] flex-col items-center justify-center p-6 text-center">
          <div
            className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
            style={{ width: "min(100%, 720px)", aspectRatio: `${VB.w} / ${VB.h}` }}
          >
            <div
              className="absolute -translate-x-1/2 -translate-y-1/2"
              style={{ left: `${(CENTER.cx / VB.w) * 100}%`, top: `${(CENTER.cy / VB.h) * 100}%` }}
            >
              <CoreHubNode state="idle" reduced={reduced} />
            </div>
          </div>
          <p className={cn(TYPE.cardTitle, "relative z-10 mt-auto")}>
            No live intelligence activity in this window
          </p>
          <p className={cn(TYPE.meta, "relative z-10 mt-1 max-w-md")}>
            Switch lenses to explore knowledge, models, and agents — or wait for new activity in the
            last {data?.windowHours ?? 24}h window.
          </p>
        </div>
      ) : topology.nodes.length === 0 ? (
        <div className="relative z-10 flex h-full min-h-[44vh] flex-col items-center justify-center p-6 text-center">
          <div
            className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
            style={{ width: "min(100%, 720px)", aspectRatio: `${VB.w} / ${VB.h}` }}
          >
            <div
              className="absolute -translate-x-1/2 -translate-y-1/2"
              style={{ left: `${(CENTER.cx / VB.w) * 100}%`, top: `${(CENTER.cy / VB.h) * 100}%` }}
            >
              <CoreHubNode state={data?.core.state ?? "idle"} reduced={reduced} />
            </div>
            {data ? (
              <CoreStats
                data={data}
                lens={lens}
                entityCount={entityCount}
                relationshipCount={relationshipCount}
                caption={topology.caption}
              />
            ) : null}
          </div>
          <p className={cn(TYPE.cardTitle, "relative z-10 mt-auto")}>{topology.caption}</p>
          <p className={cn(TYPE.meta, "relative z-10 mt-1 max-w-md")}>
            This lens has no nodes to plot yet — shown honestly, not simulated. Try another lens or
            connect more sources.
          </p>
        </div>
      ) : (
        <AnimatePresence mode="wait">
          <motion.div
            key={lens}
            initial={reduced ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={reduced ? undefined : { opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="relative z-10 h-full min-h-[44vh] w-full"
            style={{ aspectRatio: `${VB.w} / ${VB.h}` }}
          >
            <svg
              viewBox={`0 0 ${VB.w} ${VB.h}`}
              className="pointer-events-none absolute inset-0 h-full w-full"
              aria-hidden
              preserveAspectRatio="xMidYMid meet"
            >
              {topology.edges.map((edge) => {
                const from = posById.get(edge.fromId === CORE_ID ? CORE_ID : edge.fromId)
                const to = posById.get(edge.toId)
                if (!from || !to) return null
                return (
                  <g key={edge.id} opacity={edge.opacity * (edge.toId.startsWith("dept:") ? 1 : 1)}>
                    <SignalEdge
                      x1={from.x}
                      y1={from.y}
                      x2={to.x}
                      y2={to.y}
                      state={edge.state}
                      reduced={reduced}
                    />
                  </g>
                )
              })}
            </svg>

            <div
              className="absolute -translate-x-1/2 -translate-y-1/2"
              style={{ left: `${(CENTER.cx / VB.w) * 100}%`, top: `${(CENTER.cy / VB.h) * 100}%` }}
            >
              <CoreHubNode state={data?.core.state ?? "idle"} reduced={reduced} />
            </div>

            {data ? (
              <CoreStats
                data={data}
                lens={lens}
                entityCount={entityCount}
                relationshipCount={relationshipCount}
                caption={topology.caption}
              />
            ) : null}

            {topology.nodes.map((node) => {
              const pos = positions.get(node.id)
              if (!pos) return null
              const isSelected = selectedId === node.id
              const warning =
                node.kind === "department" && node.department
                  ? warningsByDept.get(node.department.id.toLowerCase())
                  : null

              return (
                <div
                  key={node.id}
                  className="absolute -translate-x-1/2 -translate-y-1/2"
                  style={{ left: `${(pos.x / VB.w) * 100}%`, top: `${(pos.y / VB.h) * 100}%` }}
                >
                  <button
                    type="button"
                    className="relative rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]"
                    onClick={() => toggleSelection(node)}
                    aria-label={`${node.label} ${node.kind} node`}
                  >
                    {node.kind === "department" && node.department ? (
                      <DepartmentNode
                        department={node.department}
                        reduced={reduced}
                        embedded
                      />
                    ) : (
                      <MapSatelliteNode node={node} reduced={reduced} selected={isSelected} />
                    )}
                  </button>
                  {warning && lens === "predicts" ? (
                    <button
                      type="button"
                      className="absolute -right-1 -top-1 z-30 flex h-6 w-6 items-center justify-center rounded-full border border-amber-500/50 bg-amber-50 text-amber-700 shadow-sm"
                      title={readString(warning.title, "Warning")}
                      onClick={(event) => {
                        event.stopPropagation()
                        onSelectionChange?.({ kind: "signal", signal: warning })
                      }}
                      aria-label={`Warning: ${readString(warning.title, "signal")}`}
                    >
                      <Warning className="h-3.5 w-3.5" weight="fill" aria-hidden />
                    </button>
                  ) : null}
                </div>
              )
            })}
          </motion.div>
        </AnimatePresence>
      )}

      {data?.note ? (
        <p className={cn(TYPE.meta, "absolute bottom-2 left-3 right-3 z-10 truncate opacity-70")}>
          {data.note}
        </p>
      ) : null}
    </div>
  )
}
