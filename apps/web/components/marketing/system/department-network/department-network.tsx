"use client"

/**
 * GravitreDepartmentNetwork — signature converge animation.
 * 3×3 CSS grid keeps every department card fully in-bounds.
 * SVG paths/packets overlay the same geometry; Nodus motion = sweeping gradients + hub rings.
 */

import { useEffect, useRef, useState } from "react"
import { AnimatePresence, motion, useInView, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"
import { GravitreDepartmentNode, type NodeVisualState } from "./department-node"
import { GravitreIntelligenceCore } from "./intelligence-core"
import { GravitreSignalPath } from "./signal-path"
import { GravitreSignalPacket } from "./signal-packet"
import { DEPARTMENT_EDGE_KEYS } from "./paths"
import { edgeKey, useNetworkStory } from "./use-network-story"
import { NETWORK_VB, type DepartmentId } from "./types"
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
  const inView = useInView(rootRef, { amount: 0.3, once: false })
  const startedRef = useRef(false)
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { state, playFromDepartment, playNextAuto, setHoverFocus } = useNetworkStory({ reduced })

  useEffect(() => {
    if (!autoplay || reduced || !inView) return
    if (!startedRef.current) {
      startedRef.current = true
      const t = setTimeout(() => {
        void playNextAuto()
      }, 500)
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
    }, 9000)
    return () => {
      if (idleTimer.current) clearTimeout(idleTimer.current)
    }
  }, [autoplay, inView, playNextAuto, reduced, state.running, state.scenarioId])

  return (
    <div ref={rootRef} className={cn("relative mx-auto w-full", className)}>
      <div className="md:hidden">
        <DepartmentNetworkMobile reduced={reduced} />
      </div>

      <div className="relative hidden md:block">
        <div
          className="relative w-full rounded-xl bg-white p-4 sm:p-5"
          style={{ aspectRatio: `${NETWORK_VB.w} / ${NETWORK_VB.h}` }}
        >
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 rounded-xl bg-[radial-gradient(var(--color-dots,#eaedf1)_1px,transparent_1px)] mask-radial-from-10% [background-size:10px_10px]"
          />

          {/* Paths behind the grid */}
          <svg
            viewBox={`0 0 ${NETWORK_VB.w} ${NETWORK_VB.h}`}
            className="pointer-events-none absolute inset-4 sm:inset-5 h-[calc(100%-2rem)] w-[calc(100%-2rem)] sm:h-[calc(100%-2.5rem)] sm:w-[calc(100%-2.5rem)]"
            aria-hidden
            preserveAspectRatio="xMidYMid meet"
          >
            {DEPARTMENT_EDGE_KEYS.map(({ dept, d }) => {
              const ek = edgeKey(dept, "core")
              const kind = state.activeEdges.get(ek) ?? null
              const muted = state.mutedDepts.has(dept) && !kind
              return (
                <GravitreSignalPath
                  key={dept}
                  d={d}
                  activeKind={kind}
                  muted={muted}
                  reduced={reduced}
                />
              )
            })}
            {!reduced
              ? state.packets.map((pkt) => (
                  <GravitreSignalPacket key={pkt.key} d={pkt.d} kind={pkt.kind} progress={pkt.progress} />
                ))
              : null}
          </svg>

          {/* In-flow 3×3 grid — cards never escape the padded stage */}
          <div className="relative z-10 grid h-full w-full grid-cols-[1fr_auto_1fr] grid-rows-[auto_1fr_auto] gap-x-3 gap-y-4">
            <div className="flex items-start justify-start">
              <GravitreDepartmentNode
                id="sales"
                state={nodeState("sales", state.activeDepts, state.resolvedDepts, state.mutedDepts)}
                interactive={!reduced}
                reduced={reduced}
                align="start"
                onHover={() => setHoverFocus("sales")}
                onLeave={() => setHoverFocus(null)}
                onClick={() => playFromDepartment("sales")}
              />
            </div>
            <div />
            <div className="flex items-start justify-end">
              <GravitreDepartmentNode
                id="support"
                state={nodeState("support", state.activeDepts, state.resolvedDepts, state.mutedDepts)}
                interactive={!reduced}
                reduced={reduced}
                align="end"
                onHover={() => setHoverFocus("support")}
                onLeave={() => setHoverFocus(null)}
                onClick={() => playFromDepartment("support")}
              />
            </div>

            <div />
            <div className="relative flex min-h-[7.5rem] items-center justify-center self-center">
              <GravitreIntelligenceCore state={state.coreState} reduced={reduced} />
            </div>
            <div />

            <div className="flex items-end justify-start">
              <GravitreDepartmentNode
                id="operations"
                state={nodeState("operations", state.activeDepts, state.resolvedDepts, state.mutedDepts)}
                interactive={!reduced}
                reduced={reduced}
                align="start"
                onHover={() => setHoverFocus("operations")}
                onLeave={() => setHoverFocus(null)}
                onClick={() => playFromDepartment("operations")}
              />
            </div>
            <div />
            <div className="flex items-end justify-end">
              <GravitreDepartmentNode
                id="finance"
                state={nodeState("finance", state.activeDepts, state.resolvedDepts, state.mutedDepts)}
                interactive={!reduced}
                reduced={reduced}
                align="end"
                onHover={() => setHoverFocus("finance")}
                onLeave={() => setHoverFocus(null)}
                onClick={() => playFromDepartment("finance")}
              />
            </div>
          </div>
        </div>

        <AnimatePresence mode="wait">
          {state.caption ? (
            <motion.p
              key={state.caption}
              initial={reduced ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduced ? undefined : { opacity: 0 }}
              className="mt-3 text-center text-sm font-medium text-[color:var(--g-text-secondary)]"
            >
              {state.caption}
            </motion.p>
          ) : (
            <p className="mt-3 text-center text-xs text-[color:var(--g-text-muted)]">
              {reduced
                ? "Departments share one governed intelligence layer."
                : "Hover a department, or click to run a short story."}
            </p>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
