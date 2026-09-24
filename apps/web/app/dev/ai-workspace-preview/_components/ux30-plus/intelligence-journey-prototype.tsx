"use client"

/**
 * Intelligence structural concepts (§21 + §40) — Field-primary vs alternatives.
 * Journey: Insight → Evidence → Relationship → Expert graph.
 * Harness only · Cesar selects Field primacy for production.
 */

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { HarnessSurface } from "./topology-primitives"

type Concept = "field-primary" | "matrix-rail" | "split-insight" | "journey" | "empty"

const STEPS = ["Insight", "Evidence", "Relationship", "Expert graph"] as const

export function IntelligenceJourneyPrototype({ scene }: { scene: string }) {
  const concept = (["field-primary", "matrix-rail", "split-insight", "journey", "empty"].find((c) =>
    scene.includes(c),
  ) ?? "field-primary") as Concept
  const [step, setStep] = useState(0)
  const [expert, setExpert] = useState<"field" | "matrix" | "kg" | "rel" | "predictive">("field")

  return (
    <div data-review-surface="intelligence-journey" data-review-scene={scene} className="mx-auto max-w-6xl space-y-4">
      <header>
        <p className={TYPE.eyebrow}>Selection C · Intelligence · SaaSFrame June Report · harness only · §21</p>
        <h2 className={cn(TYPE.pageTitle, "mt-1")}>Field-primary and alternative structures</h2>
        <p className={cn(TYPE.pageLead, "mt-2")}>
          Evidence-led Field (insight header + evidence cards + topology) — not an empty graph. Expert capability
          preserved. Production Field primacy reserved for Cesar.
        </p>
      </header>

      <div className="flex flex-wrap gap-1">
        {(
          [
            ["field-primary", "Concept 1 · Field-primary"],
            ["matrix-rail", "Concept 2 · Matrix rail"],
            ["split-insight", "Concept 3 · Split insight"],
            ["journey", "Journey walkthrough"],
            ["empty", "Empty / insufficient"],
          ] as const
        ).map(([id, label]) => (
          <Button key={id} size="sm" variant={concept === id ? "secondary" : "ghost"} asChild>
            <a href={`/dev/ai-workspace-preview?s=intelligence-journey&scene=${id}`}>{label}</a>
          </Button>
        ))}
      </div>

      {concept === "empty" && (
        <HarnessSurface className="flex min-h-[300px] flex-col justify-center p-8">
          <p className={TYPE.eyebrow}>Insufficient data</p>
          <h3 className={cn(TYPE.pageTitle, "mt-2")}>Not enough entities to render a Field</h3>
          <p className={cn(TYPE.pageLead, "mt-2 max-w-lg")}>
            Matrix would show empty cells — explain why, avoid meaningless dashes, offer Connect source / run
            workflow.
          </p>
          <div className="mt-4 flex gap-2">
            <Button size="sm">Connect source</Button>
            <Button size="sm" variant="secondary">
              Open expert Matrix anyway
            </Button>
          </div>
        </HarnessSurface>
      )}

      {concept === "journey" && (
        <HarnessSurface className="space-y-4 p-4">
          <div className="flex flex-wrap gap-2">
            {STEPS.map((s, i) => (
              <Button key={s} size="sm" variant={step === i ? "secondary" : "ghost"} onClick={() => setStep(i)}>
                {i + 1}. {s}
              </Button>
            ))}
          </div>
          {step === 0 && (
            <p className="text-sm">Insight: Acme renewal risk rose · 2 new buying signals · recommend review.</p>
          )}
          {step === 1 && (
            <p className="text-sm">Evidence: run_01 · HubSpot activity · learned relationship strength +0.12 (fixture).</p>
          )}
          {step === 2 && (
            <p className="text-sm">Relationship: Acme ↔ Roderick · works_at · confirmed knowledge node.</p>
          )}
          {step === 3 && (
            <div className="space-y-2">
              <p className="text-sm">Expert graph: Field / Matrix / KG / Relationships / Predictive — pick tool:</p>
              <div className="flex flex-wrap gap-1">
                {(["field", "matrix", "kg", "rel", "predictive"] as const).map((e) => (
                  <Button key={e} size="sm" variant={expert === e ? "secondary" : "outline"} onClick={() => setExpert(e)}>
                    {e}
                  </Button>
                ))}
              </div>
              <div className="h-40 rounded-lg border border-dashed border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)] p-3">
                <p className={TYPE.meta}>Expert surface · {expert} (fixture)</p>
              </div>
            </div>
          )}
        </HarnessSurface>
      )}

      {concept === "field-primary" && (
        <div className="space-y-3">
          <HarnessSurface className="p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className={TYPE.eyebrow}>Concept 1 · June Report zones · Field primacy</p>
                <h3 className={cn(TYPE.cardTitle, "mt-1")}>Acme renewal risk rose</h3>
                <p className={TYPE.meta}>Insight · fixture · not live production evidence</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline">
                  What changed?
                </Button>
                <Button size="sm" variant="secondary">
                  Filters
                </Button>
              </div>
            </div>
            <div className="mt-3 flex gap-1 text-xs">
              {["knows", "learns", "predicts", "acts", "improves"].map((l) => (
                <span key={l} className="rounded-md bg-[color:var(--g-intelligence-soft)] px-2 py-1 capitalize">
                  {l}
                </span>
              ))}
            </div>
          </HarnessSurface>

          <div className="grid gap-3 lg:grid-cols-[1fr_280px]">
            <div className="space-y-3">
              <div className="grid gap-2 sm:grid-cols-3">
                {[
                  ["Evidence", "run_01 · HubSpot activity"],
                  ["Relationship", "Acme ↔ Roderick · works_at"],
                  ["Next", "Review approval · enrich"],
                ].map(([t, v]) => (
                  <HarnessSurface key={t} className="p-3">
                    <p className={TYPE.meta}>{t}</p>
                    <p className="mt-1 text-sm font-medium">{v}</p>
                  </HarnessSurface>
                ))}
              </div>
              <HarnessSurface className="min-h-[280px] p-4">
                <p className={TYPE.eyebrow}>Field · owns the viewport</p>
                <div className="relative mt-3 h-56 overflow-hidden rounded-lg border border-[color:var(--g-border-default)] bg-[color:var(--g-canvas)]">
                  <svg viewBox="0 0 480 220" className="h-full w-full" aria-hidden>
                    <line x1="120" y1="110" x2="240" y2="70" stroke="var(--g-border-default)" strokeWidth="1.5" />
                    <line x1="240" y1="70" x2="360" y2="120" stroke="var(--g-border-default)" strokeWidth="1.5" />
                    <line x1="120" y1="110" x2="240" y2="160" stroke="var(--g-border-default)" strokeWidth="1.5" />
                    <rect x="70" y="90" width="100" height="40" rx="8" fill="color-mix(in oklch, var(--g-emerald) 8%, white)" stroke="var(--g-emerald)" />
                    <text x="120" y="114" textAnchor="middle" fontSize="11" fill="var(--g-text-primary)">
                      Acme Corp
                    </text>
                    <rect x="190" y="50" width="100" height="40" rx="8" fill="var(--g-surface-1)" stroke="var(--g-border-default)" />
                    <text x="240" y="74" textAnchor="middle" fontSize="11" fill="var(--g-text-primary)">
                      Roderick
                    </text>
                    <rect x="310" y="100" width="100" height="40" rx="8" fill="var(--g-surface-1)" stroke="var(--g-border-default)" />
                    <text x="360" y="124" textAnchor="middle" fontSize="11" fill="var(--g-text-primary)">
                      HubSpot
                    </text>
                    <rect x="190" y="140" width="100" height="40" rx="8" fill="color-mix(in oklch, var(--g-approval) 10%, white)" stroke="var(--g-approval)" />
                    <text x="240" y="164" textAnchor="middle" fontSize="11" fill="var(--g-text-primary)">
                      Renewal risk
                    </text>
                  </svg>
                </div>
                <div className="mt-3 flex flex-wrap gap-1">
                  <Button size="sm" variant="ghost">
                    Matrix
                  </Button>
                  <Button size="sm" variant="ghost">
                    Knowledge Graph
                  </Button>
                  <Button size="sm" variant="ghost">
                    Relationships
                  </Button>
                  <Button size="sm" variant="ghost">
                    Predictive
                  </Button>
                </div>
              </HarnessSurface>
            </div>
            <HarnessSurface className="p-4">
              <p className={TYPE.eyebrow}>Inspector</p>
              <p className="mt-2 text-sm font-medium">Acme Corp</p>
              <p className={TYPE.meta}>Evidence · Ask · Advance filters</p>
              <ul className="mt-3 space-y-2 text-xs text-[color:var(--g-text-secondary)]">
                <li className="rounded border border-[color:var(--g-border-subtle)] px-2 py-1.5">
                  Signal · buying intent +2 (fixture)
                </li>
                <li className="rounded border border-[color:var(--g-border-subtle)] px-2 py-1.5">
                  Source · HubSpot · run_01
                </li>
              </ul>
              <p className="mt-4 text-xs text-[color:var(--g-text-secondary)]">
                Pros: matches §21 overview-first. Cons: expert Matrix less visible — must stay one click away.
              </p>
            </HarnessSurface>
          </div>
        </div>
      )}

      {concept === "matrix-rail" && (
        <div className="grid gap-3 lg:grid-cols-[200px_1fr_240px]">
          <HarnessSurface className="p-3">
            <p className={TYPE.eyebrow}>Matrix rail</p>
            <ul className="mt-2 space-y-1 text-xs">
              {["Knows", "Learns", "Predicts", "Acts", "Improves"].map((r) => (
                <li key={r} className="rounded border border-[color:var(--g-border-subtle)] px-2 py-1">
                  {r} · …
                </li>
              ))}
            </ul>
          </HarnessSurface>
          <HarnessSurface className="min-h-[320px] p-4">
            <p className={TYPE.eyebrow}>Concept 2 · Field center + Matrix always visible</p>
            <div className="mt-4 h-56 rounded-lg border border-dashed border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)]" />
          </HarnessSurface>
          <HarnessSurface className="p-4">
            <p className={TYPE.eyebrow}>Tradeoff</p>
            <p className="mt-2 text-xs">Pros: expert taxonomy always present. Cons: first screen denser; empty Matrix cells risk.</p>
          </HarnessSurface>
        </div>
      )}

      {concept === "split-insight" && (
        <div className="space-y-3">
          <HarnessSurface className="p-4">
            <p className={TYPE.eyebrow}>Concept 3 · Insight strip first</p>
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              {["Renewal risk ↑", "2 buying signals", "Approve enrich"].map((t) => (
                <div key={t} className="rounded-lg border border-[color:var(--g-border-subtle)] p-3 text-sm font-medium">
                  {t}
                </div>
              ))}
            </div>
          </HarnessSurface>
          <HarnessSurface className="min-h-[240px] p-4">
            <p className={TYPE.meta}>Field secondary until drill-down · Expert tools in overflow</p>
            <div className="mt-3 h-40 rounded-lg bg-[color:var(--g-canvas)]" />
            <p className="mt-3 text-xs">Pros: actionable first. Cons: Field can feel demoted vs §21 immersive preference.</p>
          </HarnessSurface>
        </div>
      )}
    </div>
  )
}
