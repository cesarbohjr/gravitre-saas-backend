"use client"

import Link from "next/link"
import {
  NucleoApproval,
  NucleoConnector,
  NucleoIntelligence,
  NucleoWorkflow,
} from "@/components/icons/nucleo/semantic"
import { Button } from "@/components/marketing/nodus/button"
import { DivideX } from "@/components/marketing/nodus/divide"
import { MarketingPageEndCta, MarketingPageHero } from "@/components/marketing/nodus/page-shell"
import {
  AgentOrchestrationField,
  EntityConvergenceWorkbenchField,
  GibeLearningField,
} from "@/components/marketing/creative"
import { GravitreReveal, GravitreTrace } from "@/components/marketing/system/motion"
import { GravitreSection, GravitreSectionHeader } from "@/components/marketing/system/section"

const specPills = [
  { icon: NucleoConnector, label: "Connected stack" },
  { icon: NucleoIntelligence, label: "Org-scoped memory" },
  { icon: NucleoApproval, label: "Approval before writes" },
  { icon: NucleoWorkflow, label: "Governed execution" },
] as const

/**
 * Technology / GIBE page — Creative Experience System signatures.
 * GIBE Learning Loop + Orchestration + Knowledge Fabric (not generic Lucide orbit carnival).
 */
export function TechnologyPage() {
  return (
    <div className="bg-[color:var(--g-marketing-canvas)]" data-technology-legacy="0" data-kf-production="workbench">
      <MarketingPageHero
        badge="Platform technology"
        title={
          <>
            The engine inside the <span className="text-brand">one brain</span>
          </>
        }
        description="GIBE — the Gravitre Intelligent Business Engine — learns from your connected stack and routes actions through governed, human-approved execution. Memory, models, and judgment for the same brain that powers Gravitre AI, agents, and workflows."
      >
        <GravitreReveal className="mt-8 flex flex-wrap items-center justify-center gap-2.5" kind="flow">
          {specPills.map((pill) => {
            const Icon = pill.icon
            return (
              <span
                key={pill.label}
                className="inline-flex items-center gap-2 rounded-full border border-divide bg-[color:var(--g-marketing-surface)] px-3.5 py-2 text-sm font-medium text-charcoal-700"
              >
                <Icon className="h-4 w-4 text-brand" aria-hidden />
                {pill.label}
              </span>
            )
          })}
        </GravitreReveal>
        <GravitreReveal className="mt-8 flex flex-wrap items-center justify-center gap-3" delay={0.08}>
          <Button as={Link} href="/get-started">
            Start free
          </Button>
          <Button as={Link} href="/docs" variant="secondary">
            Read the docs
          </Button>
        </GravitreReveal>
      </MarketingPageHero>

      <DivideX />

      <GravitreSection>
        <GravitreSectionHeader
          align="center"
          badge="GIBE path"
          title="Observe, recommend, then human approve"
          description="An illustrative GIBE learning loop — action, observe, evaluate, advisory recommend, approve, retain. Not auto policy rewrite."
          className="mb-6"
        />
        <GravitreTrace>
          <GibeLearningField />
        </GravitreTrace>
        <p className="mt-4 text-center text-[11px] text-[color:var(--g-text-muted)]">
          <Link className="underline underline-offset-2" href="/docs/guides/how-to/org-learning">
            How org learning works
          </Link>
        </p>
      </GravitreSection>

      <DivideX />

      <GravitreSection>
        <GravitreSectionHeader
          align="center"
          badge="Orchestration"
          title="One intent, coordinated work, one verified outcome"
          description="An illustrative Task Decomposition Field — how a request can become a plan, specialized capabilities, tools, approval, and evidence. Not a live run."
          className="mb-6"
        />
        <GravitreTrace>
          <AgentOrchestrationField />
        </GravitreTrace>
      </GravitreSection>

      <DivideX />

      <GravitreSection>
        <GravitreSectionHeader
          align="center"
          badge="Knowledge Fabric"
          title="Mentions converge when the match is exact"
          description="An illustrative Entity Convergence field — normalize, exact-match, and evidence. Not fuzzy person matching. Not a live org graph."
          className="mb-6"
        />
        <GravitreTrace>
          <EntityConvergenceWorkbenchField />
        </GravitreTrace>
        <p className="mt-4 text-center text-[11px] text-[color:var(--g-text-muted)]">
          <Link className="underline underline-offset-2" href="/docs/guides/how-to/sources">
            How sources feed the fabric
          </Link>
        </p>
      </GravitreSection>

      <MarketingPageEndCta />
    </div>
  )
}
