"use client"

/**
 * GravitreDepartmentNetwork — signature "departments converge" animation.
 * Primary runtime: custom SVG + Motion. Configuration-driven scenarios.
 * GSAP scroll variant kept optional (see department-network-scroll.tsx) —
 * Motion autoplay won the Nodus calmness / performance comparison for About.
 */

import { useEffect, useRef, useState } from "react"
import { AnimatePresence, motion, useInView, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"
import { GravitreDepartmentNode, type NodeVisualState } from "./department-node"
import { GravitreIntelligenceCore } from "./intelligence-core"
import { GravitreSignalPath } from "./signal-path"
import { GravitreSignalPacket } from "./signal-packet"
import { DEPARTMENT_EDGE_KEYS, departmentPoint } from "./paths"
import { edgeKey, useNetworkStory } from "./use-network-story"
import { DEPARTMENT_META, NETWORK_VB, type DepartmentId } from "./types"
import { DepartmentNetworkMobile } from "./department-network-mobile"

function nodeState(
  id: DepartmentId,
  active: Set<DepartmentId>,
  resolved: Set<DepartmentId>,
  muted: Set<DepartmentId>,
): NodeVisualState {
  if (active.has(id)) return "active"
  if (resolved.has(id)) return "resolved"
  if (muted.has(id)) return "muted"
  return "idle"
}

export function GravitreDepartmentNetwork({
  className,
  autoplay = true,
}: {
  className?: string
  autoplay?: boolean
}) {
  const reducePreference = useReducedMotion()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  const reduced = mounted && !!reducePreference

  const rootRef = useRef<HTMLDivElement>(null)
  const inView = useInView(rootRef, { amount: 0.35, once: false })
  const startedRef = useRef(false)
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { state, playFromDepartment, playNextAuto, setHoverFocus } = useNetworkStory({ reduced })

  useEffect(() => {
    if (!autoplay || reduced || !inView) return
    if (!startedRef.current) {
      startedRef.current = true
      const t = setTimeout(() => {
        void playNextAuto()
      }, 700)
      return () => clearTimeout(t)
    }
  }, [autoplay, inView, playNextAuto, reduced])

  useEffect(() => {
    if (!autoplay || reduced || !inView) return
    if (state.running) {
      if (idleTimer.current) clearTimeout(idleTimer.current)
      return
    }
    if (!startedRef.current) return
    idleTimer.current = setTimeout(() => {
      void playNextAuto()
    }, 10000)
    return () => {
      if (idleTimer.current) clearTimeout(idleTimer.current)
    }
  }, [autoplay, inView, playNextAuto, reduced, state.running, state.scenarioId])

  return (
    <div ref={rootRef} className={cn("relative mx-auto w-full max-w-3xl", className)}>
      <div className="md:hidden">
        <DepartmentNetworkMobile reduced={reduced} />
      </div>

      <div className="relative hidden md:block">
        <svg
          viewBox={`0 0 ${NETWORK_VB.w} ${NETWORK_VB.h}`}
          className="h-auto w-full"
          role="img"
          aria-label="Departments create signals that flow through Gravitre intelligence so other teams can act, then outcomes return and shared intelligence learns"
        >
          <defs>
            <radialGradient id="gv-dept-core-field" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="color-mix(in oklch, var(--g-intelligence) 14%, transparent)" />
              <stop offset="100%" stopColor="transparent" />
            </radialGradient>
            <pattern id="gv-dept-dot-grid" width="10" height="10" patternUnits="userSpaceOnUse">
              <circle cx="1" cy="1" r="0.7" fill="var(--color-dots, #eaedf1)" />
            </pattern>
          </defs>

          <rect width={NETWORK_VB.w} height={NETWORK_VB.h} fill="#fff" />
          <rect
            width={NETWORK_VB.w}
            height={NETWORK_VB.h}
            fill="url(#gv-dept-dot-grid)"
            opacity={0.9}
            style={{
              maskImage: "radial-gradient(ellipse 70% 65% at 50% 50%, black 15%, transparent 75%)",
              WebkitMaskImage: "radial-gradient(ellipse 70% 65% at 50% 50%, black 15%, transparent 75%)",
            }}
          />

          {DEPARTMENT_EDGE_KEYS.map(({ dept, d }) => {
            const ek = edgeKey(dept, "core")
            const kind = state.activeEdges.get(ek) ?? null
            const muted = state.mutedDepts.has(dept) && !kind
            return (
              <GravitreSignalPath key={dept} d={d} activeKind={kind} muted={muted} reduced={reduced} />
            )
          })}

          {DEPARTMENT_EDGE_KEYS.map(({ dept }) => {
            const pt = departmentPoint(dept)
            const ax = NETWORK_VB.cx + (pt.x - NETWORK_VB.cx) * 0.28
            const ay = NETWORK_VB.cy + (pt.y - NETWORK_VB.cy) * 0.28
            const active = state.activeEdges.has(edgeKey(dept, "core"))
            return (
              <circle
                key={`anchor-${dept}`}
                cx={ax}
                cy={ay}
                r={2.25}
                fill={active ? "var(--color-brand, #16a374)" : "var(--color-line, #eaedf1)"}
              />
            )
          })}

          <GravitreIntelligenceCore state={state.coreState} reduced={reduced} />

          {(Object.keys(DEPARTMENT_META) as DepartmentId[]).map((id) => {
            const pt = departmentPoint(id)
            return (
              <GravitreDepartmentNode
                key={id}
                id={id}
                x={pt.x}
                y={pt.y}
                state={nodeState(id, state.activeDepts, state.resolvedDepts, state.mutedDepts)}
                interactive={!reduced}
                onHover={() => setHoverFocus(id)}
                onLeave={() => setHoverFocus(null)}
                onClick={() => playFromDepartment(id)}
              />
            )
          })}

          {!reduced
            ? state.packets.map((pkt) => (
                <GravitreSignalPacket key={pkt.key} d={pkt.d} kind={pkt.kind} progress={pkt.progress} />
              ))
            : null}
        </svg>

        <AnimatePresence mode="wait">
          {state.caption ? (
            <motion.p
              key={state.caption}
              initial={reduced ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduced ? undefined : { opacity: 0 }}
              className="mt-4 text-center text-sm font-medium text-[color:var(--g-text-secondary)]"
            >
              {state.caption}
            </motion.p>
          ) : (
            <motion.p
              key="hint"
              initial={false}
              animate={{ opacity: 0.7 }}
              className="mt-4 text-center text-xs text-[color:var(--g-text-muted)]"
            >
              {reduced
                ? "Departments share one governed intelligence layer."
                : "Hover a department, or click to run a short story."}
            </motion.p>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
