"use client"

import { useEffect, useRef, useState } from "react"
import { NucleoApproval, NucleoConnector, NucleoSuccess } from "@/components/icons/nucleo/semantic"
import { cn } from "@/lib/utils"
import { GravitreEvidenceMark } from "../../primitives/evidence-mark"
import { withCreativeScene } from "../../fallbacks/with-creative-scene"
import { useCreativePerformance } from "../../core/use-creative-performance"
import {
  CAPABILITY_PORTS,
  ILLUSTRATIVE_CONTEXT,
  PHASE_CAPTION,
  nextPhase,
  parseCfStateParam,
  showAuth,
  showEvidence,
  showPorts,
  writeDone,
  writeWaiting,
  type ConnectorPhase,
} from "./storyboard"

function ReducedModel() {
  return (
    <div className="space-y-3 text-sm text-[color:var(--g-text-secondary)]">
      <p className="font-medium">Context</p>
      <p>{ILLUSTRATIVE_CONTEXT}</p>
      <p className="font-medium">Ports</p>
      <ul className="list-disc pl-5">
        {CAPABILITY_PORTS.map((p) => (
          <li key={p.id}>
            {p.label}: {p.caps.join(" · ")}
          </li>
        ))}
      </ul>
      <GravitreEvidenceMark label="Governed write" tone="waiting" />
      <p className="text-[11px] text-[color:var(--g-text-muted)]">Not a live connector inventory.</p>
    </div>
  )
}

function ConnectorFabricFieldImpl({ className }: { className?: string }) {
  const rootRef = useRef<HTMLDivElement>(null)
  const { reducedMotion: reduced, shouldAnimate, quality } = useCreativePerformance(rootRef)
  const [frozenPhase, setFrozenPhase] = useState<ConnectorPhase | null>(null)
  const [phase, setPhase] = useState<ConnectorPhase>("quiet")

  useEffect(() => {
    if (typeof window === "undefined") return
    const frozen = parseCfStateParam(new URLSearchParams(window.location.search).get("cfState"), {
      hostname: window.location.hostname,
    })
    setFrozenPhase(frozen)
    if (frozen) setPhase(frozen)
  }, [])

  useEffect(() => {
    if (frozenPhase || !shouldAnimate) return
    const t = window.setTimeout(() => setPhase((p) => nextPhase(p)), phase === "write_waiting" ? 1600 : 1100)
    return () => window.clearTimeout(t)
  }, [phase, shouldAnimate, frozenPhase])

  const ports = showPorts(phase)
  const auth = showAuth(phase)
  const waiting = writeWaiting(phase)
  const done = writeDone(phase)
  const evidence = showEvidence(phase)

  return (
    <div
      ref={rootRef}
      className={cn("mx-auto w-full max-w-3xl", className)}
      data-testid="connector-fabric-field"
      data-creative-phase={phase}
      data-creative-frozen={frozenPhase ? "1" : "0"}
      data-creative-quality={quality}
      data-cf-write-waiting={waiting ? "1" : "0"}
      data-cf-logo-wall="0"
    >
      {reduced ? (
        <div className="rounded-2xl border border-divide bg-white p-5" data-testid="cf-reduced">
          <ReducedModel />
        </div>
      ) : (
        <div className="rounded-2xl border border-divide bg-white p-4 md:p-6" data-testid="cf-desktop">
          <p className="text-center text-sm text-[color:var(--g-text-secondary)]">{ILLUSTRATIVE_CONTEXT}</p>
          {ports ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              {CAPABILITY_PORTS.map((port) => (
                <div
                  key={port.id}
                  className={cn(
                    "rounded-xl border bg-white px-3 py-3 text-center",
                    auth ? "border-[color:var(--color-brand,#16a374)]" : "border-divide",
                  )}
                  data-testid={`cf-port-${port.id}`}
                >
                  <NucleoConnector
                    className={cn(
                      "mx-auto h-4 w-4",
                      auth ? "text-[color:var(--color-brand,#16a374)]" : "text-[color:var(--g-text-muted)]",
                    )}
                    aria-hidden
                  />
                  <p className="mt-1.5 text-xs font-semibold text-[color:var(--g-text-secondary)]">{port.label}</p>
                  <div className="mt-2 flex flex-wrap justify-center gap-1">
                    {port.caps.map((cap) => {
                      const isWrite = cap === "WRITE" || cap === "SEND"
                      const highlightWait = waiting && isWrite && port.id === "crm"
                      const highlightDone = done && isWrite && port.id === "crm"
                      return (
                        <span
                          key={cap}
                          className={cn(
                            "rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                            highlightWait && "border-amber-400 bg-amber-50 text-amber-800",
                            highlightDone && "border-[color:var(--color-brand,#16a374)] text-[color:var(--color-brand,#16a374)]",
                            !highlightWait && !highlightDone && "border-divide text-[color:var(--g-text-muted)]",
                          )}
                        >
                          {cap}
                        </span>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-6 text-center text-sm text-[color:var(--g-text-muted)]">Capability ports dormant.</p>
          )}

          {waiting ? (
            <div className="mt-4 flex justify-center" data-testid="cf-waiting">
              <GravitreEvidenceMark label="Needs approval before write" tone="waiting" />
            </div>
          ) : null}
          {done && !evidence ? (
            <div className="mt-4 flex items-center justify-center gap-1 text-xs text-[color:var(--color-brand,#16a374)]">
              <NucleoApproval className="h-3.5 w-3.5" aria-hidden />
              Same write path continues after approval
            </div>
          ) : null}
          {evidence ? (
            <div className="mt-4 flex flex-col items-center gap-1" data-testid="cf-evidence">
              <GravitreEvidenceMark label="Scopes checked" />
              <GravitreEvidenceMark label="Write executed" />
            </div>
          ) : null}
        </div>
      )}

      <p className="mt-3 text-center text-sm font-medium text-[color:var(--g-text-secondary)]" aria-live="polite">
        {reduced ? "Illustrative connector fabric model." : PHASE_CAPTION[phase]}
      </p>
      <p className="mt-2 flex items-center justify-center gap-1 text-center text-[11px] text-[color:var(--g-text-muted)]">
        <NucleoSuccess className="h-3 w-3" aria-hidden />
        Illustrative connector fabric — capability ports and governed writes. Not a live inventory of your stack.
      </p>
    </div>
  )
}

export const ConnectorFabricField = withCreativeScene(ConnectorFabricFieldImpl, "connector-fabric")
