"use client"

/**
 * Shared AI workspace compositions — harness only.
 * Places future “show the work” checklist slot without implementing live checklist/backend.
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

const SCENES: AiScene[] = [
  "conversation-primary",
  "work-primary",
  "show-the-work-slot",
  "voice-continuity",
  "split",
]

export function SharedAiWorkspacePrototype({ scene }: { scene: string }) {
  const active = (SCENES.find((s) => scene.includes(s)) ?? "conversation-primary") as AiScene

  return (
    <div data-review-surface="ai-workspace" data-review-scene={scene} className="mx-auto max-w-5xl space-y-4">
      <header>
        <p className={TYPE.eyebrow}>3.0 Plus · Shared AI workspace · harness only</p>
        <h2 className={cn(TYPE.pageTitle, "mt-1")}>Composition variants (shared vocabulary)</h2>
        <p className={cn(TYPE.pageLead, "mt-2")}>
          Consumes stable presentation vocabulary only. No second chat runtime. Show-the-work = placement, not live
          integration.
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
          "grid min-h-[320px] gap-3 rounded-xl border border-[color:var(--g-border-default)] bg-[color:var(--g-canvas)] p-3",
          active === "split" || active === "show-the-work-slot" ? "md:grid-cols-[1fr_1fr]" : "md:grid-cols-1",
          active === "work-primary" && "md:grid-cols-[280px_1fr]",
          active === "conversation-primary" && "md:grid-cols-[1fr_280px]",
        )}
      >
        {(active === "conversation-primary" ||
          active === "split" ||
          active === "show-the-work-slot" ||
          active === "voice-continuity" ||
          active === "work-primary") && (
          <HarnessSurface className="p-4">
            <p className={TYPE.eyebrow}>Conversation</p>
            <p className="mt-2 text-sm">Fixture turn — qualify Acme and request approval.</p>
            {active === "voice-continuity" && (
              <p className="mt-3 text-xs text-[color:var(--g-signal)]">Voice state: listening · text↔voice same task</p>
            )}
          </HarnessSurface>
        )}

        {(active === "work-primary" || active === "split" || active === "conversation-primary") && (
          <HarnessSurface className="p-4">
            <p className={TYPE.eyebrow}>Work / artifact</p>
            <p className="mt-2 text-sm">Contact draft · Acme Corp</p>
            <p className={TYPE.meta}>Authoritative task state from core contracts — not invented here</p>
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
