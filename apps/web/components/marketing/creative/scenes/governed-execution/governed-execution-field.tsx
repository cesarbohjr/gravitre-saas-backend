"use client"

import { useEffect, useRef, useState } from "react"
import { useInView, useReducedMotion } from "framer-motion"
import { NucleoApproval, NucleoSuccess } from "@/components/icons/nucleo/semantic"
import { cn } from "@/lib/utils"
import { GravitreEvidenceMark } from "../../primitives/evidence-mark"
import {
  GATE_STAGES,
  GOVERNED_WRITE_PATH_ID,
  ILLUSTRATIVE_CONTEXT,
  PHASE_CAPTION,
  activeStageIds,
  isWaiting,
  nextPhase,
  parseGovStateParam,
  showEvidence,
  showTrail,
  type GovernancePhase,
} from "./storyboard"

function ReducedModel() {
  return (
    <div className="space-y-3 text-sm text-[color:var(--g-text-secondary)]">
      <p className="font-medium">Context</p>
      <p>{ILLUSTRATIVE_CONTEXT}</p>
      <p className="font-medium">Path</p>
      <p>{GATE_STAGES.map((s) => s.label).join(" → ")}</p>
      <GravitreEvidenceMark label="Approval required" tone="waiting" />
      <GravitreEvidenceMark label="Audit trail remains" />
      <p className="text-[11px] text-[color:var(--g-text-muted)]">Not a live compliance claim.</p>
    </div>
  )
}

export function GovernedExecutionField({ className }: { className?: string }) {
  const reducePreference = useReducedMotion()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  const reduced = mounted && !!reducePreference

  const rootRef = useRef<HTMLDivElement>(null)
  const inView = useInView(rootRef, { amount: 0.25, once: false })
  const [hidden, setHidden] = useState(false)
  const [frozenPhase, setFrozenPhase] = useState<GovernancePhase | null>(null)
  const [phase, setPhase] = useState<GovernancePhase>("quiet")

  useEffect(() => {
    const onVis = () => setHidden(document.hidden)
    onVis()
    document.addEventListener("visibilitychange", onVis)
    return () => document.removeEventListener("visibilitychange", onVis)
  }, [])

  useEffect(() => {
    if (typeof window === "undefined") return
    const frozen = parseGovStateParam(new URLSearchParams(window.location.search).get("govState"), {
      hostname: window.location.hostname,
    })
    setFrozenPhase(frozen)
    if (frozen) setPhase(frozen)
  }, [])

  useEffect(() => {
    if (frozenPhase || reduced || !inView || hidden) return
    const t = window.setTimeout(() => setPhase((p) => nextPhase(p)), phase === "approval" ? 1600 : 1100)
    return () => window.clearTimeout(t)
  }, [phase, reduced, inView, hidden, frozenPhase])

  const lit = new Set(activeStageIds(phase))
  const waiting = isWaiting(phase)
  const evidence = showEvidence(phase)
  const trail = showTrail(phase)

  return (
    <div
      ref={rootRef}
      className={cn("mx-auto w-full max-w-3xl", className)}
      data-testid="governed-execution-field"
      data-creative-phase={phase}
      data-creative-frozen={frozenPhase ? "1" : "0"}
      data-gov-waiting={waiting ? "1" : "0"}
      data-gov-path-id={
        ["approval", "execute", "evidence", "trail", "honest"].includes(phase)
          ? GOVERNED_WRITE_PATH_ID
          : undefined
      }
    >
      {reduced ? (
        <div className="rounded-2xl border border-divide bg-white p-5" data-testid="gov-reduced">
          <ReducedModel />
        </div>
      ) : (
        <div className="rounded-2xl border border-divide bg-white p-4 md:p-6" data-testid="gov-desktop">
          <p className="text-center text-sm text-[color:var(--g-text-secondary)]">{ILLUSTRATIVE_CONTEXT}</p>

          <div className="mt-5 flex flex-wrap items-center justify-center gap-2 md:gap-3">
            {GATE_STAGES.map((stage, i) => {
              const on = lit.has(stage.id)
              const isApproval = stage.id === "approval"
              return (
                <div key={stage.id} className="flex items-center gap-2 md:gap-3">
                  <div
                    className={cn(
                      "min-w-[4.5rem] rounded-xl border px-2.5 py-2 text-center",
                      on && !waiting && "border-[color:var(--color-brand,#16a374)]",
                      on && waiting && isApproval && "border-amber-400 bg-amber-50",
                      !on && "border-divide opacity-60",
                    )}
                    data-testid={`gov-stage-${stage.id}`}
                    data-lit={on ? "1" : "0"}
                  >
                    {isApproval && waiting ? (
                      <NucleoApproval className="mx-auto h-3.5 w-3.5 text-amber-700" aria-hidden />
                    ) : null}
                    <p
                      className={cn(
                        "text-[11px] font-semibold",
                        on ? "text-[color:var(--g-text-secondary)]" : "text-[color:var(--g-text-muted)]",
                        waiting && isApproval && "text-amber-800",
                      )}
                    >
                      {stage.label}
                    </p>
                  </div>
                  {i < GATE_STAGES.length - 1 ? (
                    <span className="hidden text-[color:var(--g-text-muted)] sm:inline" aria-hidden>
                      →
                    </span>
                  ) : null}
                </div>
              )
            })}
          </div>

          {waiting ? (
            <div className="mt-4 flex justify-center" data-testid="gov-waiting">
              <GravitreEvidenceMark label="Needs approval before write" tone="waiting" />
            </div>
          ) : null}
          {evidence ? (
            <div className="mt-4 flex flex-col items-center gap-1" data-testid="gov-evidence">
              <GravitreEvidenceMark label="Write executed" />
              <GravitreEvidenceMark label="Audit event recorded" />
            </div>
          ) : null}
          {trail ? (
            <svg
              viewBox="0 0 200 8"
              className="pointer-events-none mx-auto mt-4 h-2 w-48"
              aria-hidden
              data-testid="gov-trail"
            >
              <line x1="4" y1="4" x2="196" y2="4" stroke="#16a374" strokeWidth="2" strokeLinecap="round" />
            </svg>
          ) : null}
        </div>
      )}

      <p className="mt-3 text-center text-sm font-medium text-[color:var(--g-text-secondary)]" aria-live="polite">
        {reduced ? "Illustrative governed execution model." : PHASE_CAPTION[phase]}
      </p>
      <p className="mt-2 flex items-center justify-center gap-1 text-center text-[11px] text-[color:var(--g-text-muted)]">
        <NucleoSuccess className="h-3 w-3" aria-hidden />
        Illustrative governed execution — policy, risk, approval, execute, evidence. Not a live compliance claim.
      </p>
    </div>
  )
}
