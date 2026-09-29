"use client"

/**
 * Agent workspace §40 — three meaningfully different structures.
 * Harness only.
 */

import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { HarnessSurface } from "./topology-primitives"

type Concept = "roster-detail" | "workbench" | "mission"

const CONCEPTS: { id: Concept; title: string; pros: string; cons: string }[] = [
  {
    id: "roster-detail",
    title: "Roster → detail",
    pros: "Familiar master-detail; scales to many agents; clear select/return.",
    cons: "Creation and orchestration feel secondary; multi-agent weak.",
  },
  {
    id: "workbench",
    title: "Workbench",
    pros: "Tools/knowledge/history as panes; AI + manual config together.",
    cons: "Heavier first paint; needs progressive disclosure.",
  },
  {
    id: "mission",
    title: "Mission strip",
    pros: "Outcome/assignment first; agent is means not hero.",
    cons: "Weaker for pure configuration admins.",
  },
]

export function AgentWorkspaceConceptsPrototype({ scene }: { scene: string }) {
  const concept = (CONCEPTS.find((c) => scene.includes(c.id))?.id ?? "roster-detail") as Concept
  const meta = CONCEPTS.find((c) => c.id === concept)!

  return (
    <div data-review-surface="agent-workspace" data-review-scene={scene} className="mx-auto max-w-5xl space-y-4">
      <header>
        <p className={TYPE.eyebrow}>§40 · Agent workspace concepts · harness only</p>
        <h2 className={cn(TYPE.pageTitle, "mt-1")}>Three different agent structures</h2>
      </header>

      <div className="flex flex-wrap gap-1">
        {CONCEPTS.map((c) => (
          <Button key={c.id} size="sm" variant={concept === c.id ? "secondary" : "ghost"} asChild>
            <a href={`/dev/ai-workspace-preview?s=agent-workspace&scene=${c.id}`}>{c.title}</a>
          </Button>
        ))}
      </div>

      {concept === "roster-detail" && (
        <div className="grid gap-3 md:grid-cols-[240px_1fr]">
          <HarnessSurface className="p-3">
            <p className={TYPE.eyebrow}>Roster</p>
            <ul className="mt-2 space-y-1 text-sm">
              {["Qualify lead", "Support triage", "RevOps analyst"].map((a, i) => (
                <li
                  key={a}
                  className={cn(
                    "rounded px-2 py-2",
                    i === 0 ? "bg-[color:var(--g-brand-soft)]" : "hover:bg-[color:var(--g-surface-2)]",
                  )}
                >
                  {a}
                </li>
              ))}
            </ul>
            <Button size="sm" className="mt-3 w-full">
              Create agent
            </Button>
          </HarnessSurface>
          <HarnessSurface className="p-4">
            <h3 className={TYPE.cardTitle}>Qualify lead</h3>
            <p className={TYPE.meta}>Tools · Knowledge · History · Training</p>
            <div className="mt-4 h-40 rounded-lg border border-dashed border-[color:var(--g-border-subtle)]" />
          </HarnessSurface>
        </div>
      )}

      {concept === "workbench" && (
        <div className="grid gap-3 md:grid-cols-3">
          {["Instructions + model", "Tools & connectors", "Runs & learning"].map((pane) => (
            <HarnessSurface key={pane} className="min-h-[200px] p-4">
              <p className={TYPE.eyebrow}>{pane}</p>
              <div className="mt-3 h-32 rounded bg-[color:var(--g-canvas)]" />
            </HarnessSurface>
          ))}
        </div>
      )}

      {concept === "mission" && (
        <HarnessSurface className="space-y-4 p-5">
          <div>
            <p className={TYPE.eyebrow}>Mission</p>
            <h3 className={TYPE.cardTitle}>Fill SQL pipeline this week</h3>
            <p className={TYPE.meta}>Goal · Workflow · Approvals linked</p>
          </div>
          <p className="text-sm">Agents assigned: Qualify lead · Enrich · Notify sales</p>
          <Button size="sm">Ask Gravitre to adjust</Button>
        </HarnessSurface>
      )}

      <HarnessSurface className="p-4">
        <p className={TYPE.eyebrow}>{meta.title}</p>
        <p className="mt-2 text-sm">Pros: {meta.pros}</p>
        <p className="mt-1 text-sm">Cons: {meta.cons}</p>
      </HarnessSurface>
    </div>
  )
}
