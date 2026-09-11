"use client"

/**
 * GravitreIntelligenceCoreLive — Phase 2 (2026-09-11) of the Intelligence redesign.
 *
 * Real, state-driven successor to the marketing GravitreDepartmentNetwork story:
 * same CSS + SVG + Framer Motion visual signature (decision #5 — no WebGL/Three.js),
 * but every node, edge, and label maps 1:1 to GET /api/intelligence/core/state.
 * Departments that have no real recent activity simply do not render a node —
 * this never invents a department the org has no signal for.
 */
import { useEffect, useState } from "react"
import { useReducedMotion } from "framer-motion"
import { useAuth } from "@/lib/auth-context"
import { useIntelligenceCoreState } from "@/lib/intelligence/use-core-state"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { CoreHubNode } from "./core-hub-node"
import { DepartmentNode } from "./department-node"
import { SignalEdge } from "./signal-edge"
import { radialLayout } from "./types"

const VB = { w: 640, h: 360 }
const CENTER = { cx: VB.w / 2, cy: VB.h / 2 }
const RADIUS = 130

export function GravitreIntelligenceCoreLive({ className }: { className?: string }) {
  const { user } = useAuth()
  const reducePreference = useReducedMotion()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  const reduced = mounted && !!reducePreference

  const { data, error, isLoading } = useIntelligenceCoreState(Boolean(user), 24)

  if (!user) return null

  const departments = data?.departments ?? []
  const positions = radialLayout(departments.length, { ...CENTER, radius: RADIUS })
  const hasAnyRealSignal =
    departments.length > 0 || (data?.core.pendingApprovalsTotal ?? 0) > 0 || (data?.core.activeAgentRuns ?? 0) > 0

  return (
    <section
      className={cn(
        "relative overflow-hidden rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-5 shadow-[var(--np-shadow)]",
        className,
      )}
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className={TYPE.sectionTitle}>Intelligence Core</h2>
          <p className={cn(TYPE.bodyMuted, "mt-1")}>
            {data
              ? `Real activity from the last ${data.windowHours}h — refreshes automatically.`
              : "Real, live org activity across departments."}
          </p>
        </div>
      </div>

      {error ? (
        <div className="rounded-[var(--np-radius-md)] border border-dashed border-divide bg-[color:var(--g-surface-2)] px-4 py-6 text-center">
          <p className={TYPE.cardTitle}>Unable to load live activity</p>
          <p className={cn(TYPE.meta, "mt-1")}>Try refreshing the page in a moment.</p>
        </div>
      ) : isLoading && !data ? (
        <div className="flex h-[220px] items-center justify-center">
          <span className={TYPE.bodyMuted}>Loading real activity…</span>
        </div>
      ) : !hasAnyRealSignal ? (
        <div className="rounded-[var(--np-radius-md)] border border-dashed border-divide bg-[color:var(--g-surface-2)] px-4 py-6 text-center">
          <p className={TYPE.cardTitle}>No live intelligence activity in this window</p>
          <p className={cn(TYPE.meta, "mt-1")}>
            No recommendations, predictions, agent runs, or pending approvals were recorded in the
            last {data?.windowHours ?? 24}h — shown honestly as empty, not simulated.
          </p>
        </div>
      ) : (
        <div className="relative w-full" style={{ aspectRatio: `${VB.w} / ${VB.h}` }}>
          <svg
            viewBox={`0 0 ${VB.w} ${VB.h}`}
            className="pointer-events-none absolute inset-0 h-full w-full"
            aria-hidden
            preserveAspectRatio="xMidYMid meet"
          >
            {departments.map((dept, i) => {
              const pos = positions[i]
              if (!pos) return null
              return (
                <SignalEdge
                  key={dept.id}
                  x1={CENTER.cx}
                  y1={CENTER.cy}
                  x2={pos.x}
                  y2={pos.y}
                  state={dept.state}
                  reduced={reduced}
                />
              )
            })}
          </svg>

          <div
            className="absolute -translate-x-1/2 -translate-y-1/2"
            style={{ left: `${(CENTER.cx / VB.w) * 100}%`, top: `${(CENTER.cy / VB.h) * 100}%` }}
          >
            <CoreHubNode state={data?.core.state ?? "idle"} reduced={reduced} />
          </div>

          {departments.map((dept, i) => {
            const pos = positions[i]
            if (!pos) return null
            return (
              <DepartmentNode
                key={dept.id}
                department={dept}
                reduced={reduced}
                style={{ left: `${(pos.x / VB.w) * 100}%`, top: `${(pos.y / VB.h) * 100}%` }}
              />
            )
          })}
        </div>
      )}

      {data ? (
        <p className={cn(TYPE.meta, "mt-4 border-t border-divide pt-3")}>
          {data.core.pendingApprovalsTotal > 0
            ? `${data.core.pendingApprovalsTotal} approval${data.core.pendingApprovalsTotal === 1 ? "" : "s"} pending`
            : "No pending approvals"}
          {data.core.activeAgentRuns > 0 ? ` · ${data.core.activeAgentRuns} agent run${data.core.activeAgentRuns === 1 ? "" : "s"} active` : ""}
          {" — "}
          {data.note}
        </p>
      ) : null}
    </section>
  )
}
