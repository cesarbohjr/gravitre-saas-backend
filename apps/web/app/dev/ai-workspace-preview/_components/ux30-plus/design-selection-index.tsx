"use client"

/**
 * Cesar design-selection index — single entry for Phase 6 review.
 * Harness only · links working prototypes · not production.
 */

import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { HarnessSurface } from "./topology-primitives"

type Link = { href: string; label: string; note?: string }

const SECTIONS: {
  id: string
  title: string
  decision: string
  links: Link[]
}[] = [
  {
    id: "A",
    title: "A · Page introduction & information hierarchy",
    decision: "Pick primary pattern(s) per page family — not one global header.",
    links: [
      { href: "?s=page-intro&scene=operating", label: "Operating", note: "Dashboard, Activity, Assignments" },
      { href: "?s=page-intro&scene=expert", label: "Expert", note: "Builders, Model Studio, dense ops" },
      { href: "?s=page-intro&scene=empty", label: "Empty", note: "First-run / insufficient data" },
      { href: "?s=page-intro&scene=immersive", label: "Immersive", note: "Field / canvas-first" },
      { href: "?s=page-intro&scene=compare", label: "Side-by-side compare", note: "All four + family map" },
    ],
  },
  {
    id: "B",
    title: "B · Window Manager default & transitions",
    decision: "Pick default mode + confirm docked as first-class.",
    links: [
      { href: "?s=window-manager&scene=docked", label: "Docked (proposed default)", note: "Page context visible" },
      { href: "?s=window-manager&scene=compact", label: "Compact" },
      { href: "?s=window-manager&scene=floating", label: "Floating" },
      { href: "?s=window-manager&scene=expanded", label: "Expanded" },
      { href: "?s=window-manager&scene=fullscreen", label: "Fullscreen" },
      { href: "?s=window-manager&scene=minimized", label: "Minimized" },
      { href: "?s=window-manager&scene=restored", label: "Restored", note: "Returns to last mode" },
      { href: "?s=window-manager&scene=tour", label: "Transition tour", note: "Stable fixture conversation id" },
    ],
  },
  {
    id: "C",
    title: "C · Intelligence Field-primary & expert access",
    decision: "Field primacy for production chrome — reserve for Cesar.",
    links: [
      { href: "?s=intelligence-journey&scene=field-primary", label: "Concept 1 · Field-primary", note: "Insight→Evidence→…" },
      { href: "?s=intelligence-journey&scene=matrix-rail", label: "Concept 2 · Matrix rail", note: "Matrix expert adjacent" },
      { href: "?s=intelligence-journey&scene=split-insight", label: "Concept 3 · Split insight", note: "Insight strip + Field" },
      { href: "?s=intelligence-journey&scene=journey", label: "Full journey walkthrough" },
      { href: "?s=intelligence&scene=empty", label: "Empty / insufficient data" },
      { href: "?s=intelligence&scene=field-primary", label: "Existing Field harness" },
    ],
  },
  {
    id: "D",
    title: "D · React Flow Workflow Builder (Option B)",
    decision: "Production cutover only after preservation review — not now.",
    links: [
      { href: "?s=workflow-rf&scene=design", label: "Design" },
      { href: "?s=workflow-rf&scene=live", label: "Live (fixture overlays)" },
      { href: "?s=workflow-rf&scene=explain", label: "Explain" },
      { href: "?s=workflow-rf&scene=history", label: "History (UI shell)" },
      { href: "?s=workflow-rf&scene=ai-preview", label: "AI-generated → RF preview", note: "Open in Builder CTA" },
      { href: "?s=workflow-gen", label: "AI → preview composition", note: "Standalone scene" },
    ],
  },
  {
    id: "E",
    title: "E · Shared AI workspace & artifacts",
    decision: "Composition only — runtime stays core agent.",
    links: [
      { href: "?s=ai-workspace&scene=conversation-primary", label: "Conversation primary" },
      { href: "?s=ai-workspace&scene=work-primary", label: "Work / artifact primary" },
      { href: "?s=ai-workspace&scene=split", label: "Split" },
      { href: "?s=ai-workspace&scene=voice-continuity", label: "Voice continuity" },
      { href: "?s=ai-workspace&scene=show-the-work-slot", label: "Show-the-work slot", note: "Placement only" },
    ],
  },
  {
    id: "F",
    title: "F · Model Studio",
    decision: "Standard vs Advanced progressive disclosure.",
    links: [
      { href: "?s=model-studio&scene=standard", label: "Standard user" },
      { href: "?s=model-studio&scene=advanced", label: "Advanced user" },
    ],
  },
  {
    id: "G",
    title: "Additional §40 concepts",
    decision: "Dashboard & Agent — pick structural direction later.",
    links: [
      { href: "?s=dashboard&scene=attention-first", label: "Dashboard · Attention-first" },
      { href: "?s=dashboard&scene=ops-board", label: "Dashboard · Ops board" },
      { href: "?s=dashboard&scene=outcome-rail", label: "Dashboard · Outcome rail" },
      { href: "?s=agent-workspace&scene=roster-detail", label: "Agent · Roster→detail" },
      { href: "?s=agent-workspace&scene=workbench", label: "Agent · Workbench" },
      { href: "?s=agent-workspace&scene=mission", label: "Agent · Mission strip" },
    ],
  },
]

export function DesignSelectionIndex() {
  return (
    <div data-review-surface="selection" className="mx-auto max-w-5xl space-y-6">
      <header>
        <p className={TYPE.eyebrow}>Gravitre 3.0 Plus · Phase 6 design-selection package</p>
        <h2 className={cn(TYPE.pageTitle, "mt-1")}>Cesar review index</h2>
        <p className={cn(TYPE.pageLead, "mt-2")}>
          Working harness previews only. Authority:{" "}
          <code className="font-mono text-xs">docs/design/GRAVITRE_3_0_PLUS_MASTER_SPEC.md</code>. Not Phase 8.
          Fixture state ≠ production execution.
        </p>
      </header>

      <HarnessSurface className="p-4">
        <p className={TYPE.eyebrow}>How to review</p>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-[color:var(--g-text-secondary)]">
          <li>Open each section’s links below in this harness.</li>
          <li>Compare structural differences (layout / hierarchy / interaction), not cosmetics.</li>
          <li>Record selections in the Cesar decision list (docs/design/3.0-plus/17-design-selection-package.md).</li>
          <li>Do not approve Phase 8 from text alone — use these previews + screenshots.</li>
        </ol>
      </HarnessSurface>

      {SECTIONS.map((section) => (
        <HarnessSurface key={section.id} className="p-4" data-selection-section={section.id}>
          <h3 className={TYPE.cardTitle}>{section.title}</h3>
          <p className={cn(TYPE.meta, "mt-1")}>{section.decision}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {section.links.map((link) => (
              <Button key={link.href} size="sm" variant="secondary" asChild>
                <a href={`/dev/ai-workspace-preview${link.href}`}>
                  {link.label}
                  {link.note ? <span className="ml-1 opacity-70">· {link.note}</span> : null}
                </a>
              </Button>
            ))}
          </div>
        </HarnessSurface>
      ))}
    </div>
  )
}
