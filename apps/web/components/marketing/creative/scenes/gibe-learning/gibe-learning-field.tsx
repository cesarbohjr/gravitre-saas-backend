"use client"

import { useEffect, useRef, useState } from "react"
import { useInView, useReducedMotion } from "framer-motion"
import { NucleoApproval, NucleoIntelligence, NucleoSuccess } from "@/components/icons/nucleo/semantic"
import { cn } from "@/lib/utils"
import { GravitreEvidenceMark } from "../../primitives/evidence-mark"
import { withCreativeScene } from "../../fallbacks/with-creative-scene"
import {
  GIBE_PREFERENCE_PATH_ID,
  ILLUSTRATIVE_CONTEXT,
  LOOP_STAGES,
  PHASE_CAPTION,
  activeStageIds,
  isAdvisory,
  isWaiting,
  nextPhase,
  parseGibeStateParam,
  showRetain,
  type GibePhase,
} from "./storyboard"

function ReducedModel() {
  return (
    <div className="space-y-3 text-sm text-[color:var(--g-text-secondary)]">
      <p className="font-medium">Context</p>
      <p>{ILLUSTRATIVE_CONTEXT}</p>
      <p className="font-medium">Loop</p>
      <p>{LOOP_STAGES.map((s) => s.label).join(" → ")}</p>
      <GravitreEvidenceMark label="Recommend is advisory" tone="waiting" />
      <GravitreEvidenceMark label="Human approve before retain" />
      <p className="text-[11px] text-[color:var(--g-text-muted)]">Not auto policy rewrite.</p>
    </div>
  )
}

function GibeLearningFieldImpl({ className }: { className?: string }) {
  const reducePreference = useReducedMotion()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  const reduced = mounted && !!reducePreference

  const rootRef = useRef<HTMLDivElement>(null)
  const inView = useInView(rootRef, { amount: 0.25, once: false })
  const [hidden, setHidden] = useState(false)
  const [frozenPhase, setFrozenPhase] = useState<GibePhase | null>(null)
  const [phase, setPhase] = useState<GibePhase>("quiet")

  useEffect(() => {
    const onVis = () => setHidden(document.hidden)
    onVis()
    document.addEventListener("visibilitychange", onVis)
    return () => document.removeEventListener("visibilitychange", onVis)
  }, [])

  useEffect(() => {
    if (typeof window === "undefined") return
    const frozen = parseGibeStateParam(new URLSearchParams(window.location.search).get("gibeState"), {
      hostname: window.location.hostname,
    })
    setFrozenPhase(frozen)
    if (frozen) setPhase(frozen)
  }, [])

  useEffect(() => {
    if (frozenPhase || reduced || !inView || hidden) return
    const delay = phase === "approve" || phase === "recommend" ? 1600 : 1100
    const t = window.setTimeout(() => setPhase((p) => nextPhase(p)), delay)
    return () => window.clearTimeout(t)
  }, [phase, reduced, inView, hidden, frozenPhase])

  const lit = new Set(activeStageIds(phase))
  const waiting = isWaiting(phase)
  const advisory = isAdvisory(phase)
  const retain = showRetain(phase)

  return (
    <div
      ref={rootRef}
      className={cn("mx-auto w-full max-w-3xl", className)}
      data-testid="gibe-learning-field"
      data-creative-phase={phase}
      data-creative-frozen={frozenPhase ? "1" : "0"}
      data-gibe-waiting={waiting ? "1" : "0"}
      data-gibe-advisory={advisory ? "1" : "0"}
      data-gibe-path-id={
        ["recommend", "approve", "retain", "honest"].includes(phase) ? GIBE_PREFERENCE_PATH_ID : undefined
      }
    >
      {reduced ? (
        <div className="rounded-2xl border border-divide bg-white p-5" data-testid="gibe-reduced">
          <ReducedModel />
        </div>
      ) : (
        <div className="rounded-2xl border border-divide bg-white p-4 md:p-6" data-testid="gibe-desktop">
          <p className="text-center text-sm text-[color:var(--g-text-secondary)]">{ILLUSTRATIVE_CONTEXT}</p>

          <div className="mt-5 flex flex-wrap items-center justify-center gap-2 md:gap-3">
            {LOOP_STAGES.map((stage, i) => {
              const on = lit.has(stage.id)
              const isRecommend = stage.id === "recommend"
              const isApprove = stage.id === "approve"
              return (
                <div key={stage.id} className="flex items-center gap-2 md:gap-3">
                  <div
                    className={cn(
                      "min-w-[4.25rem] rounded-xl border px-2.5 py-2 text-center",
                      on && !waiting && !advisory && "border-[color:var(--color-brand,#16a374)]",
                      on && advisory && isRecommend && "border-[color:var(--g-intelligence)] bg-slate-50",
                      on && waiting && isApprove && "border-amber-400 bg-amber-50",
                      !on && "border-divide opacity-60",
                    )}
                    data-testid={`gibe-stage-${stage.id}`}
                    data-lit={on ? "1" : "0"}
                  >
                    {isRecommend && advisory ? (
                      <NucleoIntelligence className="mx-auto h-3.5 w-3.5 text-[color:var(--g-intelligence)]" aria-hidden />
                    ) : null}
                    {isApprove && waiting ? (
                      <NucleoApproval className="mx-auto h-3.5 w-3.5 text-amber-700" aria-hidden />
                    ) : null}
                    <p
                      className={cn(
                        "text-[11px] font-semibold",
                        on ? "text-[color:var(--g-text-secondary)]" : "text-[color:var(--g-text-muted)]",
                        waiting && isApprove && "text-amber-800",
                      )}
                    >
                      {stage.label}
                    </p>
                  </div>
                  {i < LOOP_STAGES.length - 1 ? (
                    <span className="hidden text-[color:var(--g-text-muted)] sm:inline" aria-hidden>
                      →
                    </span>
                  ) : null}
                </div>
              )
            })}
          </div>

          {advisory ? (
            <div className="mt-4 flex justify-center" data-testid="gibe-advisory">
              <GravitreEvidenceMark label="Advisory recommendation" tone="waiting" />
            </div>
          ) : null}
          {waiting ? (
            <div className="mt-4 flex justify-center" data-testid="gibe-waiting">
              <GravitreEvidenceMark label="Needs human approval" tone="waiting" />
            </div>
          ) : null}
          {retain ? (
            <div className="mt-4 flex flex-col items-center gap-1" data-testid="gibe-retain">
              <GravitreEvidenceMark label="Preferred path retained" />
              <svg
                viewBox="0 0 200 8"
                className="pointer-events-none mt-2 h-2 w-48"
                aria-hidden
                data-testid="gibe-retain-trail"
              >
                <line x1="4" y1="4" x2="196" y2="4" stroke="#16a374" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </div>
          ) : null}
        </div>
      )}

      <p className="mt-3 text-center text-sm font-medium text-[color:var(--g-text-secondary)]" aria-live="polite">
        {reduced ? "Illustrative GIBE learning loop." : PHASE_CAPTION[phase]}
      </p>
      <p className="mt-2 flex items-center justify-center gap-1 text-center text-[11px] text-[color:var(--g-text-muted)]">
        <NucleoSuccess className="h-3 w-3" aria-hidden />
        Illustrative GIBE loop — observe, evaluate, recommend, human approve. Not auto policy rewrite.
      </p>
    </div>
  )
}

export const GibeLearningField = withCreativeScene(GibeLearningFieldImpl, "gibe-learning")
