"use client"

/**
 * Page introduction / information-hierarchy variants — harness only.
 * Operating · Expert · Empty · Immersive — Cesar structural selection.
 */

import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { HarnessSurface } from "./topology-primitives"

type IntroVariant = "operating" | "expert" | "empty" | "immersive"

const VARIANTS: IntroVariant[] = ["operating", "expert", "empty", "immersive"]

export function PageIntroVariantsPrototype({ scene }: { scene: string }) {
  const variant = (VARIANTS.find((v) => scene.includes(v)) ?? "operating") as IntroVariant

  return (
    <div data-review-surface="page-intro" data-review-scene={scene} className="mx-auto max-w-5xl space-y-4">
      <header>
        <p className={TYPE.eyebrow}>3.0 Plus · Page introduction variants · harness only</p>
        <h2 className={cn(TYPE.pageTitle, "mt-1")}>Information hierarchy — pick one structural direction</h2>
        <p className={cn(TYPE.pageLead, "mt-2")}>
          Same route intent (Intelligence). Different intro / primacy. Not production chrome.
        </p>
      </header>

      <div className="flex flex-wrap gap-1">
        {VARIANTS.map((v) => (
          <Button key={v} size="sm" variant={variant === v ? "secondary" : "ghost"} asChild>
            <a href={`/dev/ai-workspace-preview?s=page-intro&scene=${v}`}>{v}</a>
          </Button>
        ))}
      </div>

      {variant === "operating" && (
        <HarnessSurface className="space-y-4 p-5">
          <div>
            <p className={TYPE.eyebrow}>Operating</p>
            <h3 className={cn(TYPE.pageTitle, "mt-1")}>Intelligence</h3>
            <p className={cn(TYPE.pageLead, "mt-1")}>What changed · what needs attention · what to do next.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {["Needs attention", "Running", "Next action"].map((label) => (
              <div key={label} className="rounded-lg border border-[color:var(--g-border-subtle)] p-3">
                <p className={TYPE.meta}>{label}</p>
                <p className="mt-1 text-sm font-medium">Fixture strip</p>
              </div>
            ))}
          </div>
          <div className="h-40 rounded-lg border border-dashed border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)]" />
        </HarnessSurface>
      )}

      {variant === "expert" && (
        <HarnessSurface className="p-5">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className={TYPE.eyebrow}>Expert</p>
              <h3 className={cn(TYPE.pageTitle, "mt-1")}>Intelligence</h3>
            </div>
            <p className="font-mono text-[11px] text-[color:var(--g-text-muted)]">
              entities 128 · rel 412 · lens knows
            </p>
          </div>
          <p className={cn(TYPE.meta, "mt-2")}>Dense metadata first · Field fills remaining viewport</p>
          <div className="mt-4 h-56 rounded-lg border border-[color:var(--g-border-default)] bg-[color:var(--g-canvas)]" />
        </HarnessSurface>
      )}

      {variant === "empty" && (
        <HarnessSurface className="flex min-h-[320px] flex-col items-start justify-center p-8">
          <p className={TYPE.eyebrow}>Empty / first-run</p>
          <h3 className={cn(TYPE.pageTitle, "mt-2")}>No knowledge fabric yet</h3>
          <p className={cn(TYPE.pageLead, "mt-2 max-w-md")}>
            Connect a source or run a workflow that writes entities. Do not invent demo graph density.
          </p>
          <Button className="mt-4" size="sm">
            Connect source
          </Button>
        </HarnessSurface>
      )}

      {variant === "immersive" && (
        <div className="overflow-hidden rounded-xl border border-[color:var(--g-border-default)]">
          <div className="relative h-[420px] bg-[color:var(--g-canvas)]">
            <div className="absolute inset-0 opacity-80">
              <div className="absolute left-1/4 top-1/3 h-3 w-3 rounded-full bg-[color:var(--g-intelligence)]" />
              <div className="absolute left-1/2 top-1/2 h-3 w-3 rounded-full bg-[color:var(--g-brand)]" />
              <div className="absolute left-2/3 top-1/4 h-3 w-3 rounded-full bg-[color:var(--g-signal)]" />
            </div>
            <div className="absolute left-4 top-4 max-w-sm rounded-lg border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)]/95 p-3 backdrop-blur-sm">
              <p className={TYPE.eyebrow}>Immersive</p>
              <h3 className={cn(TYPE.cardTitle, "mt-1")}>Field is the page</h3>
              <p className={TYPE.meta}>Title + one line overlay · chrome recedes</p>
            </div>
          </div>
        </div>
      )}

      <HarnessSurface className="p-4">
        <p className={TYPE.eyebrow}>Selection note</p>
        <p className="mt-2 text-sm">
          Cesar picks one primary intro pattern (or route-specific mapping). Prototype authorization ≠ production
          choice.
        </p>
      </HarnessSurface>
    </div>
  )
}
