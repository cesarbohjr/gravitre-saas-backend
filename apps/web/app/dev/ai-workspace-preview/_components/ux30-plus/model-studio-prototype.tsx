"use client"

/**
 * Model Studio structural prototype — harness only (§22).
 * Standard vs Advanced progressive disclosure. Fixture data — not live model APIs.
 */

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { HarnessSurface } from "./topology-primitives"

type Level = "standard" | "advanced"

const FIXTURE_MODELS = [
  {
    id: "m-builtin-1",
    name: "Gravitre ops reasoner",
    purpose: "Workflow planning + tool selection",
    status: "active",
    performance: "p95 1.2s · fixture",
    kind: "built-in",
  },
  {
    id: "m-custom-1",
    name: "Churn classifier",
    purpose: "Customer churn analysis",
    status: "evaluating",
    performance: "F1 0.81 · fixture",
    kind: "custom",
  },
]

export function ModelStudioPrototype({ scene }: { scene: string }) {
  const level: Level = scene.includes("advanced") ? "advanced" : "standard"
  const [selected, setSelected] = useState(FIXTURE_MODELS[0].id)
  const model = FIXTURE_MODELS.find((m) => m.id === selected) ?? FIXTURE_MODELS[0]

  return (
    <div data-review-surface="model-studio" data-review-scene={scene} className="mx-auto max-w-5xl space-y-4">
      <header>
        <p className={TYPE.eyebrow}>3.0 Plus · Model Studio · harness only · §22</p>
        <h2 className={cn(TYPE.pageTitle, "mt-1")}>Model Studio — progressive disclosure</h2>
        <p className={cn(TYPE.pageLead, "mt-2")}>
          Mandatory redesign surface. Standard users see purpose/status/actions; Advanced reveals
          configuration/evaluation/training fields. Fixture only — no provider calls.
        </p>
      </header>

      <div className="flex flex-wrap gap-1">
        <Button size="sm" variant={level === "standard" ? "secondary" : "ghost"} asChild>
          <a href="/dev/ai-workspace-preview?s=model-studio&scene=standard">Standard</a>
        </Button>
        <Button size="sm" variant={level === "advanced" ? "secondary" : "ghost"} asChild>
          <a href="/dev/ai-workspace-preview?s=model-studio&scene=advanced">Advanced</a>
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-[240px_1fr]">
        <HarnessSurface className="p-3">
          <p className={TYPE.eyebrow}>Models</p>
          <ul className="mt-2 space-y-1">
            {FIXTURE_MODELS.map((m) => (
              <li key={m.id}>
                <button
                  type="button"
                  className={cn(
                    "w-full rounded-md px-2 py-2 text-left text-sm",
                    selected === m.id
                      ? "bg-[color:var(--g-brand-soft)] text-[color:var(--g-text-primary)]"
                      : "hover:bg-[color:var(--g-surface-2)]",
                  )}
                  onClick={() => setSelected(m.id)}
                >
                  <span className="font-medium">{m.name}</span>
                  <span className="mt-0.5 block text-[11px] text-[color:var(--g-text-muted)]">{m.kind}</span>
                </button>
              </li>
            ))}
          </ul>
        </HarnessSurface>

        <HarnessSurface className="space-y-4 p-4">
          <div>
            <p className={TYPE.eyebrow}>{model.kind}</p>
            <h3 className={cn(TYPE.cardTitle, "mt-1")}>{model.name}</h3>
            <p className="mt-1 text-sm text-[color:var(--g-text-secondary)]">{model.purpose}</p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <p className={TYPE.meta}>Status</p>
              <p className="text-sm font-medium">{model.status}</p>
            </div>
            <div>
              <p className={TYPE.meta}>Performance</p>
              <p className="text-sm font-medium">{model.performance}</p>
            </div>
            <div>
              <p className={TYPE.meta}>Used for</p>
              <p className="text-sm font-medium">{model.purpose}</p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button size="sm">Recommended: keep default</Button>
            <Button size="sm" variant="secondary">
              View usage
            </Button>
          </div>

          {level === "advanced" ? (
            <div className="space-y-3 border-t border-[color:var(--g-border-subtle)] pt-4">
              <p className={TYPE.eyebrow}>Advanced</p>
              <div className="grid gap-3 sm:grid-cols-2">
                {["Provider mapping", "Evaluation suite", "Training job", "Augmentation", "Parameters", "Permissions"].map(
                  (label) => (
                    <div
                      key={label}
                      className="rounded-lg border border-dashed border-[color:var(--g-border-subtle)] p-3"
                    >
                      <p className="text-sm font-medium">{label}</p>
                      <p className={TYPE.meta}>Progressive field group — wire to live contracts later</p>
                    </div>
                  ),
                )}
              </div>
            </div>
          ) : (
            <p className={cn(TYPE.meta, "border-t border-[color:var(--g-border-subtle)] pt-3")}>
              Advanced configuration hidden until needed (§22 progressive disclosure).
            </p>
          )}
        </HarnessSurface>
      </div>
    </div>
  )
}
