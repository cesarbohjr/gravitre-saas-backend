"use client"

/**
 * SaaSFrame research → design trace — Phase 6 harness.
 * Shows REF → PATTERN → INTERPRETATION → PREVIEW for Cesar.
 */

import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { HarnessSurface } from "./topology-primitives"

const TRACES: {
  id: string
  gravitre: string
  sourceUrl: string
  sourceLabel: string
  pattern: string
  interpretation: string
  preview: string
  previewLabel: string
  notCopied: string
  preserved: string
}[] = [
  {
    id: "dash",
    gravitre: "Dashboard",
    sourceUrl: "https://www.saasframe.io/examples/wise-dashboard",
    sourceLabel: "Wise Dashboard",
    pattern: "Narrow rail · hero status · accent primary action · entity cards · activity list",
    interpretation: "Needs-you hero + Resolve next + running/changed + activity table (fixture)",
    preview: "?s=dashboard&scene=attention-first",
    previewLabel: "Open updated Dashboard",
    notCopied: "Wise green brand, currency UX, promo banners",
    preserved: "Approvals, failed runs, connectors, Intelligence change signals",
  },
  {
    id: "intro",
    gravitre: "Page introduction (Operating)",
    sourceUrl: "https://www.saasframe.io/examples/mintlify-dashboard",
    sourceLabel: "Mintlify Dashboard",
    pattern: "Greeting + secondary actions · progress stepper · hero status card · activity",
    interpretation: "Replace equal 3-card KPI strip with stepper + primary work card + activity",
    preview: "?s=page-intro&scene=operating",
    previewLabel: "Open Operating intro",
    notCopied: "Mintlify brand, decorative docs thumbnails",
    preserved: "Family→pattern map; Approvals / Field secondary actions",
  },
  {
    id: "intel",
    gravitre: "Intelligence overview",
    sourceUrl: "https://www.saasframe.io/examples/june-report",
    sourceLabel: "June Report",
    pattern: "Sticky zones · insight header · filters · card segments · summary→detail",
    interpretation: "Insight + evidence cards + Field canvas — not empty graph viewport",
    preview: "?s=intelligence-journey&scene=field-primary",
    previewLabel: "Open Field-primary",
    notCopied: "Vanity analytics charts without business meaning",
    preserved: "Insight→Evidence→Relationship→Expert; Matrix/KG tools",
  },
  {
    id: "ai",
    gravitre: "AI workspace",
    sourceUrl: "https://www.saasframe.io/examples/hugging-face-interactive-ai-space",
    sourceLabel: "HF Interactive AI Space",
    pattern: "Prompt · AI Generation State (streaming/complete/regenerate) · output pane",
    interpretation: "Fixture generation states beside conversation + artifact (no second runtime)",
    preview: "?s=ai-workspace&scene=generating",
    previewLabel: "Open generating state",
    notCopied: "HF community chrome / model zoo",
    preserved: "Core chat API/SSE, artifacts, voice; show-the-work = placement only",
  },
  {
    id: "wm",
    gravitre: "Window Manager",
    sourceUrl: "https://www.saasframe.io/examples/dust-chat-interface",
    sourceLabel: "Dust Chat Interface",
    pattern: "Sidebar + chat feed + prompt dock; page context can remain visible",
    interpretation: "Docked WM keeps underlying page; stable fixture conversation/task ids",
    preview: "?s=window-manager&scene=docked",
    previewLabel: "Open docked WM",
    notCopied: "Dust branding / agent marketplace look",
    preserved: "No remount of core agent conversation/taskState",
  },
  {
    id: "agent",
    gravitre: "Agent workspace",
    sourceUrl: "https://www.saasframe.io/examples/dust-chat-interface",
    sourceLabel: "Dust Chat (roster patterns)",
    pattern: "Rail list + detail + create; chat/work split vocabulary",
    interpretation: "Roster→detail with Tools/Knowledge/History slots (fixture)",
    preview: "?s=agent-workspace&scene=roster-detail",
    previewLabel: "Open Agent roster",
    notCopied: "External agent SKUs / prices / Enable toggles",
    preserved: "Existing agent configuration capabilities",
  },
  {
    id: "model",
    gravitre: "Model Studio",
    sourceUrl: "https://www.saasframe.io/examples/mintlify-dashboard",
    sourceLabel: "Mintlify progressive disclosure",
    pattern: "Purpose/status first; advanced config revealed later",
    interpretation: "Standard purpose/actions; Advanced provider/eval/training groups",
    preview: "?s=model-studio&scene=standard",
    previewLabel: "Open Model Studio",
    notCopied: "Fake TRAINED badges or live provider claims",
    preserved: "Built-in vs custom models as product concepts",
  },
]

export function SaaSFrameResearchTrace({ scene: _scene }: { scene: string }) {
  return (
    <div data-review-surface="saasframe" className="mx-auto max-w-5xl space-y-5">
      <header>
        <p className={TYPE.eyebrow}>SaaSFrame mandatory research · harness only · §8.4</p>
        <h2 className={cn(TYPE.pageTitle, "mt-1")}>Research → pattern → Gravitre → preview</h2>
        <p className={cn(TYPE.pageLead, "mt-2")}>
          Nodus/Gravitre visual system applied to structures extracted from inspected SaaSFrame screens. Not a clone.
          Full mapping: <code className="font-mono text-xs">docs/design/3.0-plus/19-saasframe-research-mapping.md</code>
        </p>
      </header>

      <HarnessSurface className="space-y-2 p-4">
        <p className={TYPE.eyebrow}>Access note</p>
        <p className="text-sm text-[color:var(--g-text-secondary)]">
          Free tier: Wise + Mintlify dashboard screens inspected visually; HF + Dust example pages inspected for pattern
          tags and composition. SaaSFrame Pro (173+ dashboards, Figma) not available — those screens are not claimed
          as inspected.
        </p>
        <div className="flex flex-wrap gap-2 pt-1">
          <Button size="sm" variant="secondary" asChild>
            <a href="https://www.saasframe.io/categories/dashboard" target="_blank" rel="noreferrer">
              SaaSFrame · Dashboard
            </a>
          </Button>
          <Button size="sm" variant="secondary" asChild>
            <a href="https://www.saasframe.io/patterns/ai-generation-state" target="_blank" rel="noreferrer">
              SaaSFrame · AI generation state
            </a>
          </Button>
        </div>
      </HarnessSurface>

      {TRACES.map((t) => (
        <HarnessSurface key={t.id} className="space-y-3 p-4" data-saasframe-trace={t.id}>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <h3 className={TYPE.cardTitle}>{t.gravitre}</h3>
            <Button size="sm" asChild>
              <a href={`/dev/ai-workspace-preview${t.preview}`}>{t.previewLabel}</a>
            </Button>
          </div>
          <dl className="space-y-2 text-sm">
            <div className="grid gap-1 sm:grid-cols-[7.5rem_1fr]">
              <dt className={TYPE.eyebrow}>SaaSFrame</dt>
              <dd>
                <a
                  className="text-[color:var(--g-brand)] underline-offset-2 hover:underline"
                  href={t.sourceUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  {t.sourceLabel}
                </a>
              </dd>
            </div>
            <div className="grid gap-1 sm:grid-cols-[7.5rem_1fr]">
              <dt className={TYPE.eyebrow}>Pattern</dt>
              <dd className="text-[color:var(--g-text-secondary)]">{t.pattern}</dd>
            </div>
            <div className="grid gap-1 sm:grid-cols-[7.5rem_1fr]">
              <dt className={TYPE.eyebrow}>Gravitre</dt>
              <dd className="text-[color:var(--g-text-secondary)]">{t.interpretation}</dd>
            </div>
            <div className="grid gap-1 sm:grid-cols-[7.5rem_1fr]">
              <dt className={TYPE.eyebrow}>Not copied</dt>
              <dd className="text-[color:var(--g-text-muted)]">{t.notCopied}</dd>
            </div>
            <div className="grid gap-1 sm:grid-cols-[7.5rem_1fr]">
              <dt className={TYPE.eyebrow}>Preserved</dt>
              <dd className="text-[color:var(--g-text-muted)]">{t.preserved}</dd>
            </div>
          </dl>
        </HarnessSurface>
      ))}
    </div>
  )
}
