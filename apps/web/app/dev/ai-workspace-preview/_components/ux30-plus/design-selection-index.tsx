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

type Section = {
  id: string
  title: string
  problem: string
  options: string
  structural: string
  preserved: string
  interaction: string
  responsive: string
  tradeoffs: string
  dependencies: string
  cesarChoice: string
  links: Link[]
}

const SECTIONS: Section[] = [
  {
    id: "A",
    title: "A · Page introduction & information hierarchy",
    problem: "First viewport must orient the operator without inventing KPI dashboards or burying the page job.",
    options: "Operating · Expert · Empty · Immersive (+ side-by-side compare).",
    structural:
      "Operating = title + lead + primary actions; Expert = denser meta/tools; Empty = honest insufficient-data; Immersive = canvas/field-first chrome.",
    preserved: "Existing route jobs and nested navigation; no production page rewrite.",
    interaction: "Scene chips switch intro pattern; compare shows all four + proposed family map.",
    responsive: "Operating compact scene demonstrates stacked lead/actions without KPI strips.",
    tradeoffs: "One global header fails; family mapping needed. Immersive hides secondary actions.",
    dependencies: "Design tokens / TYPE only — no AI runtime.",
    cesarChoice: "Approve family→pattern map (or amend) before Phase 8 page work.",
    links: [
      { href: "?s=page-intro&scene=operating", label: "Operating", note: "Dashboard, Activity, Assignments" },
      { href: "?s=page-intro&scene=expert", label: "Expert", note: "Builders, Model Studio" },
      { href: "?s=page-intro&scene=empty", label: "Empty", note: "First-run / insufficient data" },
      { href: "?s=page-intro&scene=immersive", label: "Immersive", note: "Field / canvas-first" },
      { href: "?s=page-intro&scene=compare", label: "Side-by-side compare", note: "All four + family map" },
    ],
  },
  {
    id: "B",
    title: "B · Window Manager default & transitions",
    problem: "Operators need page context + AI work without remounting conversation/task state.",
    options: "Docked (proposed default) · Compact · Floating · Expanded · Fullscreen · Minimized · Restored · Tour.",
    structural: "Docked keeps page visible beside AI; fullscreen covers page; minimized is chrome-only restore target.",
    preserved: "Stable fixture conversationId / taskId across mode changes (continuity contract).",
    interaction: "Mode chips + tour walk transitions; restore returns to last mode.",
    responsive: "Compact + docked are the primary narrow-width paths; floating may obscure canvas.",
    tradeoffs: "Docked = less immersive; fullscreen = deep work but hides page.",
    dependencies: "Core owns conversation/taskState/voice — WM must not remount (composition only).",
    cesarChoice: "Pick production default mode (proposal: docked).",
    links: [
      { href: "?s=window-manager&scene=docked", label: "Docked (proposed default)", note: "Page context visible" },
      { href: "?s=window-manager&scene=compact", label: "Compact" },
      { href: "?s=window-manager&scene=floating", label: "Floating" },
      { href: "?s=window-manager&scene=expanded", label: "Expanded" },
      { href: "?s=window-manager&scene=fullscreen", label: "Fullscreen" },
      { href: "?s=window-manager&scene=minimized", label: "Minimized" },
      { href: "?s=window-manager&scene=restored", label: "Restored", note: "Returns to last mode" },
      { href: "?s=window-manager&scene=tour", label: "Transition tour", note: "Stable fixture ids" },
    ],
  },
  {
    id: "C",
    title: "C · Intelligence Field-primary & expert access",
    problem: "Intelligence overview must lead with Field insight while keeping Matrix/expert one click away.",
    options: "Field-primary · Matrix rail · Split insight · Full journey · Empty states.",
    structural: "Field-primary = Field owns viewport; Matrix rail = expert adjacent; Split = insight strip + Field demoted.",
    preserved: "Journey Insight→Evidence→Relationship→Expert; empty/insufficient-data honesty.",
    interaction: "Concept scenes + journey walkthrough; existing Field harness still linked.",
    responsive: "Field primacy must remain readable when Matrix collapses to drawer/step.",
    tradeoffs: "Matrix-always-visible densifies empty cells; split demotes Field vs §21.",
    dependencies: "Fixture graph only — no live Intelligence API in harness.",
    cesarChoice: "Field primacy for production chrome? Which of the 3 concepts?",
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
    problem: "Visual builder quality without losing Meson/decision/council/version/live-run capabilities.",
    options: "Design · Live · Explain · History · AI→RF preview · workflow-gen composition.",
    structural: "Isolated @xyflow visual layer; canvasToSavePayload demonstrated; production builder untouched.",
    preserved:
      "Gaps still visible: Meson apply · decision multi-handles · council UI · version restore API · live runsApi overlays.",
    interaction: "Mode chips; node/edge inspect; Open in Builder CTA from AI preview (fixture).",
    responsive: "Canvas pans/zooms; inspector stacks on narrow widths in harness.",
    tradeoffs: "Working prototype ≠ cutover. Gaps must close before production RF.",
    dependencies: "Shared CanvasWorkflowNode schema; execute/dryRun/runsApi remain core; Meson shared until RF cutover.",
    cesarChoice: "Defer production cutover until preservation review (14-option-b-preservation-evidence.md).",
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
    problem: "Compose conversation vs work/artifact primacy without forking chat execution.",
    options: "Conversation-primary · Work-primary · Split · Voice continuity · Show-the-work slot.",
    structural: "Layout compositions only; show-the-work is a placement slot (not the live feature).",
    preserved: "Core agent owns chat API/SSE, artifacts contracts, voice execution.",
    interaction: "Scene chips change pane primacy; fixture artifacts only.",
    responsive: "Split stacks on compact; conversation/work primacy for narrow focus.",
    tradeoffs: "Work-primary hides chat; conversation-primary buries artifacts.",
    dependencies: "Hard no-edit: ai-workspace.tsx, chat-execution-panel, ai-work-canvas, gravitre-command-os, chat API/SSE.",
    cesarChoice: "Pick composition direction for later Phase 8 chrome (runtime stays core).",
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
    problem: "Standard users need purpose/status/actions; experts need config without dumping all fields first.",
    options: "Standard user · Advanced user (progressive disclosure).",
    structural: "Standard = model purpose + status + recommended actions; Advanced reveals provider/eval/training groups.",
    preserved: "No provider/training calls — fixture labels only (no invented Enable/prices).",
    interaction: "standard/advanced scene chips toggle field groups.",
    responsive: "Advanced grid stacks; Standard remains single-column readable.",
    tradeoffs: "Advanced density vs Standard clarity; must not fake TRAINED/live claims.",
    dependencies: "Later wire to live Model Studio contracts — harness is visual only.",
    cesarChoice: "Confirm Standard/Advanced progressive disclosure as the direction.",
    links: [
      { href: "?s=model-studio&scene=standard", label: "Standard user" },
      { href: "?s=model-studio&scene=advanced", label: "Advanced user" },
    ],
  },
  {
    id: "G",
    title: "Additional §40 concepts",
    problem: "Dashboard and Agent need structural directions distinct from current chrome — concepts only.",
    options: "Dashboard: Attention-first · Ops board · Outcome rail. Agent: Roster→detail · Workbench · Mission strip.",
    structural: "Three meaningfully different layouts each; not cosmetic variants.",
    preserved: "No production Dashboard/Agent route rewrite; fixture content.",
    interaction: "Scene chips switch concepts; no live ops data.",
    responsive: "Attention-first and roster-detail are the compact-friendly baselines.",
    tradeoffs: "Ops board denser; mission strip narrative vs workbench density.",
    dependencies: "Optional picks — not blocking A–F.",
    cesarChoice: "Optional: pick Dashboard + Agent structural direction when ready.",
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

function MetaRow({ label, children }: { label: string; children: string }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[9rem_1fr] sm:gap-3">
      <dt className={cn(TYPE.eyebrow, "sm:pt-0.5")}>{label}</dt>
      <dd className="text-sm text-[color:var(--g-text-secondary)]">{children}</dd>
    </div>
  )
}

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
          <li>Open each section’s links below in this harness (same tab).</li>
          <li>Compare structural differences (layout / hierarchy / interaction), not cosmetics.</li>
          <li>
            Offline backup screenshots:{" "}
            <code className="font-mono text-[11px]">docs/design/3.0-plus/selection-shots/</code>
          </li>
          <li>Record selections in the checklist at the bottom — do not approve Phase 8 from text alone.</li>
        </ol>
      </HarnessSurface>

      {SECTIONS.map((section) => (
        <HarnessSurface key={section.id} className="space-y-4 p-4" data-selection-section={section.id}>
          <div>
            <h3 className={TYPE.cardTitle}>{section.title}</h3>
            <p className={cn(TYPE.meta, "mt-1")}>
              <span className="font-medium text-[color:var(--g-text)]">Cesar chooses:</span> {section.cesarChoice}
            </p>
          </div>

          <dl className="space-y-2 border-t border-[color:var(--g-border)] pt-3">
            <MetaRow label="Problem">{section.problem}</MetaRow>
            <MetaRow label="Visual options">{section.options}</MetaRow>
            <MetaRow label="Structure">{section.structural}</MetaRow>
            <MetaRow label="Preserved">{section.preserved}</MetaRow>
            <MetaRow label="Interaction">{section.interaction}</MetaRow>
            <MetaRow label="Responsive">{section.responsive}</MetaRow>
            <MetaRow label="Tradeoffs">{section.tradeoffs}</MetaRow>
            <MetaRow label="Dependencies">{section.dependencies}</MetaRow>
          </dl>

          <div className="flex flex-wrap gap-2 border-t border-[color:var(--g-border)] pt-3">
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

      <HarnessSurface className="space-y-3 p-4">
        <p className={TYPE.eyebrow}>Cesar decision checklist (reserved — not agent-chosen)</p>
        <ul className="space-y-2 text-sm">
          <li>
            <strong>A</strong> — Page-intro map by family (Operating / Expert / Empty / Immersive)
          </li>
          <li>
            <strong>B</strong> — Window Manager default mode (proposed: docked)
          </li>
          <li>
            <strong>C</strong> — Intelligence Field primacy + which of 3 concepts
          </li>
          <li>
            <strong>D</strong> — React Flow production cutover deferred; review gaps (Meson apply, multi-handles,
            council, version restore, live runsApi)
          </li>
          <li>
            <strong>E</strong> — AI workspace composition direction (runtime stays core agent)
          </li>
          <li>
            <strong>F</strong> — Model Studio Standard/Advanced progressive disclosure
          </li>
          <li>
            <strong>§40</strong> — Optional Dashboard + Agent structural picks
          </li>
        </ul>
        <p className={cn(TYPE.meta, "mt-2")}>
          Evidence:{" "}
          <code className="font-mono text-[11px]">docs/design/3.0-plus/18-design-selection-reviewability.md</code>
        </p>
      </HarnessSurface>
    </div>
  )
}
