"use client"

/**
 * Dashboard §40 — three meaningfully different structural concepts.
 * Harness only · SaaSFrame-informed hierarchy · Nodus/Gravitre visual.
 */

import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { HarnessSurface } from "./topology-primitives"

type Concept = "attention-first" | "ops-board" | "outcome-rail"

const CONCEPTS: { id: Concept; title: string; pros: string; cons: string }[] = [
  {
    id: "attention-first",
    title: "Attention-first",
    pros: "Answers what requires action now; clear primary CTA; matches §16 questions.",
    cons: "Weaker for scanning many healthy systems; risk of alert fatigue.",
  },
  {
    id: "ops-board",
    title: "Ops board",
    pros: "Running / failed / approvals as columns; operator muscle memory.",
    cons: "Can look like generic kanban; business outcomes secondary.",
  },
  {
    id: "outcome-rail",
    title: "Outcome rail",
    pros: "Business outcomes lead; AI work nested under goals.",
    cons: "Harder when goals empty; more progressive-disclosure work.",
  },
]

export function DashboardConceptsPrototype({ scene }: { scene: string }) {
  const concept = (CONCEPTS.find((c) => scene.includes(c.id))?.id ?? "attention-first") as Concept
  const meta = CONCEPTS.find((c) => c.id === concept)!

  return (
    <div data-review-surface="dashboard" data-review-scene={scene} className="mx-auto max-w-5xl space-y-4">
      <header>
        <p className={TYPE.eyebrow}>§40 · Dashboard structural concepts · harness only</p>
        <h2 className={cn(TYPE.pageTitle, "mt-1")}>Three different structures</h2>
        <p className={cn(TYPE.pageLead, "mt-2")}>
          Not card rearrangements. What matters / changed / running / attention / next — no decorative KPIs.
        </p>
      </header>

      <div className="flex flex-wrap gap-1">
        {CONCEPTS.map((c) => (
          <Button key={c.id} size="sm" variant={concept === c.id ? "secondary" : "ghost"} asChild>
            <a href={`/dev/ai-workspace-preview?s=dashboard&scene=${c.id}`}>{c.title}</a>
          </Button>
        ))}
      </div>

      {concept === "attention-first" && (
        <HarnessSurface className="space-y-4 p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className={TYPE.cardTitle}>Needs you</h3>
              <p className={TYPE.meta}>2 approvals · 1 failed run · 1 connector degraded</p>
            </div>
            <Button size="sm">Resolve next</Button>
          </div>
          <ul className="space-y-2 text-sm">
            <li className="rounded-lg border border-[color:var(--g-warning)]/40 p-3">Approve HubSpot write · Acme</li>
            <li className="rounded-lg border border-[color:var(--g-danger)]/40 p-3">Prospect enrich failed · step 3</li>
            <li className="rounded-lg border border-[color:var(--g-border-subtle)] p-3">Apollo connector · auth expiring</li>
          </ul>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-dashed border-[color:var(--g-border-subtle)] p-3">
              <p className={TYPE.meta}>Running now</p>
              <p className="text-sm">Qualify lead · 2/4</p>
            </div>
            <div className="rounded-lg border border-dashed border-[color:var(--g-border-subtle)] p-3">
              <p className={TYPE.meta}>Changed</p>
              <p className="text-sm">3 Intelligence updates · open Field</p>
            </div>
          </div>
        </HarnessSurface>
      )}

      {concept === "ops-board" && (
        <div className="grid gap-3 md:grid-cols-3">
          {[
            ["Running", ["Qualify lead", "Sync contacts"]],
            ["Blocked", ["Approve outreach", "Connector auth"]],
            ["Done today", ["Enrich batch", "Report draft"]],
          ].map(([col, items]) => (
            <HarnessSurface key={col as string} className="p-3">
              <p className={TYPE.eyebrow}>{col as string}</p>
              <ul className="mt-2 space-y-2 text-sm">
                {(items as string[]).map((i) => (
                  <li key={i} className="rounded border border-[color:var(--g-border-subtle)] px-2 py-2">
                    {i}
                  </li>
                ))}
              </ul>
            </HarnessSurface>
          ))}
        </div>
      )}

      {concept === "outcome-rail" && (
        <HarnessSurface className="p-5">
          <h3 className={TYPE.cardTitle}>Outcomes</h3>
          <div className="mt-4 space-y-3">
            {[
              ["Pipeline health", "Workflows 2 · Agents 1 · Ask"],
              ["Renewals this month", "Intelligence signals · Approval"],
            ].map(([goal, under]) => (
              <div key={goal} className="rounded-lg border border-[color:var(--g-border-default)] p-4">
                <p className="font-medium">{goal}</p>
                <p className={TYPE.meta}>{under}</p>
                <Button size="sm" className="mt-2" variant="secondary">
                  Continue
                </Button>
              </div>
            ))}
          </div>
        </HarnessSurface>
      )}

      <HarnessSurface className="p-4">
        <p className={TYPE.eyebrow}>{meta.title} · tradeoffs</p>
        <p className="mt-2 text-sm">
          <span className="font-medium">Pros:</span> {meta.pros}
        </p>
        <p className="mt-1 text-sm">
          <span className="font-medium">Cons:</span> {meta.cons}
        </p>
      </HarnessSurface>
    </div>
  )
}
