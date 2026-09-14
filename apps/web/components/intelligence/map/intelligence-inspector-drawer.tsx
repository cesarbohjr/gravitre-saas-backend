"use client"

/**
 * G5 — Contextual inspection / evidence drawer for Intelligence map selections.
 * Collapsed by default; opens when a map node is selected.
 */
import Link from "next/link"
import { useEffect, useMemo } from "react"
import { useIntelligenceExperienceOptional } from "@/components/intelligence/shell/intelligence-experience-provider"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import type { IntelligenceMapSelection } from "./intelligence-map"
import type { IntelligencePageContextResponse } from "@/lib/api"
import type { AllDepartmentsPayload } from "@/components/intelligence/why-gravitre-panel"
import { resolveInspectorContext } from "@/lib/intelligence/resolve-inspector-context"
import { EvidenceGraphCanvas, EvidenceGraphMeta } from "@/components/intelligence/evidence-graph-canvas"
import { buildEvidenceGraph } from "@/components/intelligence/evidence-graph-topology"
import { APP_ROUTES } from "@/lib/app-routes"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { ArrowRight, Robot, Warning } from "@phosphor-icons/react"

export function IntelligenceInspectorDrawer({
  selection,
  onSelectionChange,
  pageContext,
  whyData,
  onAskAbout,
}: {
  selection: IntelligenceMapSelection
  onSelectionChange: (selection: IntelligenceMapSelection) => void
  pageContext?: IntelligencePageContextResponse | null
  whyData?: AllDepartmentsPayload | null
  /** Prefill Ask Gravitre with a contextual question. */
  onAskAbout?: (question: string) => void
}) {
  const experience = useIntelligenceExperienceOptional()
  const open = selection != null
  const context = useMemo(
    () => (selection ? resolveInspectorContext(selection, pageContext, whyData) : null),
    [selection, pageContext, whyData],
  )

  const evidenceGraphMeta = useMemo(() => {
    if (!context?.priorityEvidence) return null
    return buildEvidenceGraph(context.priorityEvidence).meta
  }, [context?.priorityEvidence])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onSelectionChange(null)
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [open, onSelectionChange])

  const agentHref =
    selection?.kind === "agent" ? `${APP_ROUTES.agents}/${selection.agent.id}` : null

  return (
    <Sheet
      modal={!experience?.inspectorPinned}
      open={open}
      onOpenChange={(next) => {
        if (!next && !experience?.inspectorPinned) onSelectionChange(null)
      }}
    >
      <SheetContent
        side="right"
        data-testid="intelligence-inspector-drawer"
        className="flex w-full flex-col gap-0 overflow-hidden p-0 sm:max-w-md"
        aria-describedby={context ? "inspector-drawer-description" : undefined}
      >
        {context ? (
          <>
            <SheetHeader className="border-b border-divide px-5 py-4 text-left">
              <div className="flex items-start gap-2">
                {selection?.kind === "signal" ? (
                  <Warning className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" weight="fill" />
                ) : selection?.kind === "agent" ? (
                  <Robot className="mt-0.5 h-5 w-5 shrink-0 text-[color:var(--g-intelligence)]" />
                ) : null}
                <div className="min-w-0 flex-1">
                  <p className={TYPE.eyebrow}>{context.eyebrow}</p>
                  <SheetTitle className={TYPE.sectionTitle}>{context.title}</SheetTitle>
                  {context.summary ? (
                    <SheetDescription id="inspector-drawer-description" className="mt-1">
                      {context.summary}
                    </SheetDescription>
                  ) : null}
                </div>
              </div>
            </SheetHeader>

            <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
              {context.facts.length > 0 ? (
                <section>
                  <h3 className={TYPE.eyebrow}>Live context</h3>
                  <dl className={cn(TYPE.meta, "mt-2 space-y-2")}>
                    {context.facts.map((fact) => (
                      <div key={fact.label} className="flex justify-between gap-3">
                        <dt className="text-[color:var(--g-text-muted)]">{fact.label}</dt>
                        <dd className="text-right font-medium capitalize text-[color:var(--g-text-primary)]">
                          {fact.value}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </section>
              ) : null}

              {context.evidence.length > 0 ? (
                <section>
                  <h3 className={TYPE.eyebrow}>Evidence</h3>
                  <ul className="mt-2 space-y-1.5">
                    {context.evidence.map((line, index) => (
                      <li
                        key={`${line}-${index}`}
                        className="rounded-md border border-divide bg-[color:var(--g-surface-2)]/50 px-3 py-2 text-xs text-[color:var(--g-text-secondary)]"
                      >
                        {line}
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}

              {context.priorityEvidence ? (
                <section>
                  <h3 className={TYPE.eyebrow}>Why Gravitre thinks this</h3>
                  <p className={cn(TYPE.meta, "mt-1")}>
                    Scored priority evidence — signals and connected sources for this insight.
                  </p>
                  <EvidenceGraphCanvas
                    item={context.priorityEvidence}
                    className="mt-3 min-h-[180px]"
                  />
                  {evidenceGraphMeta ? (
                    <EvidenceGraphMeta
                      item={context.priorityEvidence}
                      capturedAt={whyData?.capturedAt}
                      meta={evidenceGraphMeta}
                      className="mt-3"
                    />
                  ) : null}
                </section>
              ) : null}

              {context.qualityFlags.length > 0 ? (
                <section>
                  <h3 className={TYPE.eyebrow}>Quality notes</h3>
                  <ul className="mt-2 flex flex-wrap gap-1.5">
                    {context.qualityFlags.map((flag) => (
                      <li
                        key={flag}
                        className="rounded-full border border-amber-500/30 bg-amber-50/80 px-2.5 py-0.5 text-[10px] font-medium text-amber-800"
                      >
                        {flag}
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}

              {context.provenance ? (
                <p className={cn(TYPE.meta, "border-t border-divide pt-3")}>
                  Source: {context.provenance}
                </p>
              ) : null}
            </div>

            <div className="flex flex-wrap gap-2 border-t border-divide px-5 py-4">
              {experience ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => experience.setInspectorPinned(!experience.inspectorPinned)}
                >
                  {experience.inspectorPinned ? "Unpin drawer" : "Pin drawer"}
                </Button>
              ) : null}
              {context.askPrompt && onAskAbout ? (
                <Button
                  type="button"
                  size="sm"
                  onClick={() => onAskAbout(context.askPrompt!)}
                >
                  Ask Gravitre why
                </Button>
              ) : (
                <Button type="button" size="sm" variant="outline" asChild>
                  <Link href="/ai">
                    Ask Gravitre
                    <ArrowRight className="ml-1 h-3 w-3" />
                  </Link>
                </Button>
              )}
              {agentHref ? (
                <Button type="button" size="sm" variant="outline" asChild>
                  <Link href={agentHref}>
                    Open agent
                    <ArrowRight className="ml-1 h-3 w-3" />
                  </Link>
                </Button>
              ) : null}
              {selection?.kind === "signal" ? (
                <Button type="button" size="sm" variant="outline" asChild>
                  <Link href={APP_ROUTES.connectors}>Connectors</Link>
                </Button>
              ) : null}
            </div>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
