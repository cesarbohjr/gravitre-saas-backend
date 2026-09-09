"use client"

/**
 * GravitreDepartmentNetwork — signature converge animation.
 * HTML stage for nodes/core (fits the page) + SVG Bézier paths/packets.
 * Motion elements borrowed from Nodus (sweeping path gradients, hub conic rings)
 * — not a clone of the homepage layout.
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

  const depts = Object.keys(DEPARTMENT_META) as DepartmentId[]

  return (
    <div ref={rootRef} className={cn("relative mx-auto w-full max-w-2xl", className)}>
      <div className="md:hidden">
        <DepartmentNetworkMobile reduced={reduced} />
      </div>

      <div className="relative hidden md:block">
        {/* Fixed aspect stage — nodes stay inside via % positions */}
        <div
          className="relative w-full overflow-hidden rounded-xl bg-white"
          style={{ aspectRatio: `${NETWORK_VB.w} / ${NETWORK_VB.h}` }}
        >
          {/* Dot field */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(var(--color-dots,#eaedf1)_1px,transparent_1px)] mask-radial-from-10% [background-size:10px_10px]"
          />

          {/* SVG paths + packets only */}
          <svg
            viewBox={`0 0 ${NETWORK_VB.w} ${NETWORK_VB.h}`}
            className="absolute inset-0 h-full w-full"
            aria-hidden
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

          <GravitreIntelligenceCore state={state.coreState} reduced={reduced} />

          {depts.map((id) => (
            <GravitreDepartmentNode
              key={id}
              id={id}
              state={nodeState(id, state.activeDepts, state.resolvedDepts, state.mutedDepts)}
              interactive={!reduced}
              onHover={() => setHoverFocus(id)}
              onLeave={() => setHoverFocus(null)}
              onClick={() => playFromDepartment(id)}
            />
          ))}
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
