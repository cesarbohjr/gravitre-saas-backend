"use client"

/**
 * G-STRUCT decision surface — Cesar selection checklist.
 * Harness only · does not authorize Phase 8 · does not invent Cesar choices.
 */

import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { HarnessSurface } from "./topology-primitives"

const NOW = [
  {
    id: "A1–A2",
    title: "Page introduction vocabulary + family map",
    ask: "Approve Operating / Expert / Empty / Immersive vocabulary and preliminary family map (or amend).",
    href: "?s=page-intro&scene=compare",
  },
  {
    id: "A3",
    title: "Window Manager default policy",
    ask: "A · Contextual default + remembered preference  —or—  B · Single default + explicit switch.",
    href: "?s=window-manager&scene=tour",
  },
  {
    id: "A4–A5",
    title: "Intelligence structure + journey",
    ask: "Field-primary · Matrix rail · Split insight — plus confirm Insight→Evidence→Relationship→Expert preserved.",
    href: "?s=intelligence-journey&scene=field-primary",
  },
  {
    id: "A6–A7",
    title: "AI workspace + Model Studio",
    ask: "Composition direction; Standard/Advanced progressive disclosure. Runtime stays core agent.",
    href: "?s=ai-workspace&scene=split",
  },
  {
    id: "A8",
    title: "React Flow Option B (direction only)",
    ask: "Preferred visual-layer direction — NOT production cutover. Gaps remain (Meson, multi-handles, council, restore, runsApi).",
    href: "?s=workflow-rf&scene=design",
  },
]

const FOCUSED = [
  { label: "WM tour (stable ids)", href: "?s=window-manager&scene=tour" },
  { label: "Intelligence empty", href: "?s=intelligence-journey&scene=empty" },
  { label: "RF fixture graph", href: "?s=workflow-rf&scene=design" },
  { label: "AI generation states", href: "?s=ai-workspace&scene=generating" },
  { label: "SaaSFrame research trace", href: "?s=saasframe" },
]

export function GStructDecisionPackage({ scene: _scene }: { scene: string }) {
  return (
    <div data-review-surface="g-struct" className="mx-auto max-w-5xl space-y-5">
      <header>
        <p className={TYPE.eyebrow}>G-STRUCT · structural selection · harness only</p>
        <h2 className={cn(TYPE.pageTitle, "mt-1")}>Decide structure — then authorize Phase 8 Slice 0</h2>
        <p className={cn(TYPE.pageLead, "mt-2")}>
          This harness validates architecture and interaction choices. It is not the finished product. Full package:{" "}
          <code className="font-mono text-xs">docs/design/3.0-plus/20-g-struct-decision-package.md</code>
        </p>
      </header>

      <HarnessSurface className="space-y-2 p-4">
        <p className={TYPE.eyebrow}>Status</p>
        <ul className="list-disc space-y-1 pl-5 text-sm text-[color:var(--g-text-secondary)]">
          <li>
            <strong>HARNESS VALIDATED</strong> (partial) — structural options are reviewable.
          </li>
          <li>
            <strong>PRODUCTION INTEGRATION PENDING</strong> — no production migration yet.
          </li>
          <li>
            <strong>HUMAN ACCEPTANCE PENDING</strong> — Cesar has not signed G-STRUCT.
          </li>
        </ul>
      </HarnessSurface>

      <HarnessSurface className="space-y-3 p-4">
        <p className={TYPE.eyebrow}>A · Select now</p>
        {NOW.map((item) => (
          <div
            key={item.id}
            className="flex flex-wrap items-start justify-between gap-3 border-t border-[color:var(--g-border-subtle)] pt-3 first:border-0 first:pt-0"
          >
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">
                {item.id} · {item.title}
              </p>
              <p className={cn(TYPE.meta, "mt-1")}>{item.ask}</p>
            </div>
            <Button size="sm" variant="secondary" asChild>
              <a href={`/dev/ai-workspace-preview${item.href}`}>Open</a>
            </Button>
          </div>
        ))}
      </HarnessSurface>

      <HarnessSurface className="space-y-3 p-4">
        <p className={TYPE.eyebrow}>B · Focused demos (optional before select)</p>
        <div className="flex flex-wrap gap-2">
          {FOCUSED.map((f) => (
            <Button key={f.href} size="sm" variant="ghost" asChild>
              <a href={`/dev/ai-workspace-preview${f.href}`}>{f.label}</a>
            </Button>
          ))}
        </div>
      </HarnessSurface>

      <HarnessSurface className="space-y-2 p-4">
        <p className={TYPE.eyebrow}>C · Phase 8 only (do not block G-STRUCT)</p>
        <p className="text-sm text-[color:var(--g-text-secondary)]">
          Full route production fidelity · authenticated Intelligence · RF cutover · live SSE/voice · show-the-work
          stream · Computer Use · G-PROOF journeys.
        </p>
      </HarnessSurface>

      <HarnessSurface className="space-y-3 p-4">
        <p className={TYPE.eyebrow}>First production slice (after G-STRUCT + explicit authorize)</p>
        <ol className="list-decimal space-y-1 pl-5 text-sm text-[color:var(--g-text-secondary)]">
          <li>Tokens + typography</li>
          <li>Shared interaction primitives</li>
          <li>Window Manager presentation shell (no second runtime)</li>
        </ol>
        <p className={TYPE.meta}>Broad Phase 8 and RF production cutover require separate authorization.</p>
      </HarnessSurface>
    </div>
  )
}
