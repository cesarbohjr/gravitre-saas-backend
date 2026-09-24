"use client"

/**
 * Shared AI workspace — SaaSFrame HF AI Generation State + Dust Chat patterns.
 * Harness only · fixture generation states · no second chat runtime.
 */

import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { HarnessSurface } from "./topology-primitives"

type AiScene =
  | "conversation-primary"
  | "work-primary"
  | "show-the-work-slot"
  | "voice-continuity"
  | "split"
  | "generating"
  | "streaming"
  | "complete"
  | "needs-approval"

const SCENES: AiScene[] = [
  "conversation-primary",
  "work-primary",
  "split",
  "generating",
  "streaming",
  "complete",
  "needs-approval",
  "show-the-work-slot",
  "voice-continuity",
]

const GEN_COPY: Partial<Record<AiScene, { label: string; detail: string }>> = {
  generating: { label: "Generating…", detail: "Planning qualify-Acme steps (fixture)" },
  streaming: { label: "Streaming", detail: "Drafting HubSpot contact fields…" },
  complete: { label: "Complete", detail: "Artifact ready · Contact draft · Acme Corp" },
  "needs-approval": { label: "Needs approval", detail: "PendingAction · HubSpot write" },
}

export function SharedAiWorkspacePrototype({ scene }: { scene: string }) {
  const active = (SCENES.find((s) => scene.includes(s)) ?? "conversation-primary") as AiScene
  const gen = GEN_COPY[active]
  const isGen = Boolean(gen)

  return (
    <div data-review-surface="ai-workspace" data-review-scene={scene} className="mx-auto max-w-5xl space-y-4">
      <header>
        <p className={TYPE.eyebrow}>AI workspace · SaaSFrame HF generation + Dust chat · harness only</p>
        <h2 className={cn(TYPE.pageTitle, "mt-1")}>Task states & compositions</h2>
        <p className={cn(TYPE.pageLead, "mt-2")}>
          Explicit generation states (loading / streaming / complete / regenerate / approval). Fixture only — core
          agent owns runtime.
        </p>
      </header>

      <div className="flex flex-wrap gap-1">
        {SCENES.map((s) => (
          <Button key={s} size="sm" variant={active === s ? "secondary" : "ghost"} asChild>
            <a href={`/dev/ai-workspace-preview?s=ai-workspace&scene=${s}`}>{s}</a>
          </Button>
        ))}
      </div>

      <div
        className={cn(
          "grid min-h-[340px] gap-3 rounded-xl border border-[color:var(--g-border-default)] bg-[color:var(--g-canvas)] p-3",
          active === "split" || active === "show-the-work-slot" || isGen
            ? "md:grid-cols-[1fr_1fr]"
            : "md:grid-cols-1",
          active === "work-primary" && "md:grid-cols-[280px_1fr]",
          active === "conversation-primary" && "md:grid-cols-[1fr_280px]",
        )}
      >
        <HarnessSurface className="flex flex-col p-4">
          <div className="flex items-center justify-between gap-2">
            <p className={TYPE.eyebrow}>Conversation</p>
            {gen && (
              <span className="rounded-md bg-[color:var(--g-brand-soft)] px-2 py-0.5 text-[11px] font-medium text-[color:var(--g-brand)]">
                {gen.label}
              </span>
            )}
          </div>
          <p className="mt-2 text-sm">Qualify Acme inbound and open HubSpot contact if SQL.</p>
          {active === "voice-continuity" && (
            <p className="mt-3 text-xs text-[color:var(--g-signal)]">Voice state: listening · text↔voice same task</p>
          )}
          {isGen && (
            <div className="mt-4 space-y-2">
              <p className={TYPE.meta}>{gen!.detail}</p>
              {(active === "generating" || active === "streaming") && (
                <div className="h-1.5 overflow-hidden rounded-full bg-[color:var(--g-border-subtle)]">
                  <div
                    className={cn(
                      "h-full rounded-full bg-[color:var(--g-brand)]",
                      active === "generating" ? "w-1/3" : "w-2/3",
                    )}
                  />
                </div>
              )}
              <div className="flex flex-wrap gap-2 pt-1">
                {active === "complete" && (
                  <>
                    <Button size="sm" variant="secondary">
                      Regenerate
                    </Button>
                    <Button size="sm">Open artifact</Button>
                  </>
                )}
                {active === "needs-approval" && <Button size="sm">Review approval</Button>}
                {(active === "generating" || active === "streaming") && (
                  <Button size="sm" variant="ghost">
                    Stop
                  </Button>
                )}
              </div>
            </div>
          )}
          <div className="mt-auto border-t border-[color:var(--g-border-subtle)] pt-3">
            <div className="rounded-lg border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] px-3 py-2 text-xs text-[color:var(--g-text-muted)]">
              Prompt dock (fixture) — Ask Gravitre…
            </div>
          </div>
        </HarnessSurface>

        {(active === "work-primary" ||
          active === "split" ||
          active === "conversation-primary" ||
          isGen) && (
          <HarnessSurface className="p-4">
            <p className={TYPE.eyebrow}>Work / artifact</p>
            <p className="mt-2 text-sm font-medium">Contact draft · Acme Corp</p>
            <p className={TYPE.meta}>Authoritative task state from core contracts — not invented here</p>
            {active === "complete" && (
              <ul className="mt-3 space-y-1 text-sm text-[color:var(--g-text-secondary)]">
                <li>Name · Acme Corp</li>
                <li>Owner · fixture@gravitre</li>
                <li>Next · request approval</li>
              </ul>
            )}
            {active === "needs-approval" && (
              <div className="mt-3 rounded-lg border border-[color:var(--g-warning)]/40 p-3 text-sm">
                PendingAction · HubSpot create contact (fixture)
              </div>
            )}
          </HarnessSurface>
        )}

        {active === "show-the-work-slot" && (
          <HarnessSurface className="border-[color:var(--g-brand)]/40 p-4">
            <p className={TYPE.eyebrow}>Show the work · placement only</p>
            <p className="mt-2 text-sm font-medium">Live execution checklist (reserved)</p>
            <ul className="mt-3 space-y-2 text-xs text-[color:var(--g-text-muted)]">
              <li className="rounded border border-dashed border-[color:var(--g-border-subtle)] px-2 py-1">
                Step slot — wired after core product completion
              </li>
              <li className="rounded border border-dashed border-[color:var(--g-border-subtle)] px-2 py-1">
                Not simulated browser / computer-use activity
              </li>
            </ul>
          </HarnessSurface>
        )}
      </div>
    </div>
  )
}
