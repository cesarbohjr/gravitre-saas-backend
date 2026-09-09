"use client"

import Link from "next/link"
import {
  NucleoApproval,
  NucleoConnector,
  NucleoIntelligence,
  NucleoWorkflow,
} from "@/components/icons/nucleo/semantic"
import { FeaturesLegacyContent } from "@/components/marketing/features/legacy-page"
import { Button } from "@/components/marketing/nodus/button"
import { DivideX } from "@/components/marketing/nodus/divide"
import { MarketingPageEndCta, MarketingPageHero } from "@/components/marketing/nodus/page-shell"
import { GibeTraceVisual } from "@/components/marketing/system/gibe-trace-visual"
import { GravitreReveal, GravitreTrace } from "@/components/marketing/system/motion"
import { GravitreSection, GravitreSectionHeader } from "@/components/marketing/system/section"

const specPills = [
  { icon: NucleoConnector, label: "Connected stack" },
  { icon: NucleoIntelligence, label: "Org-scoped memory" },
  { icon: NucleoApproval, label: "Approval before writes" },
  { icon: NucleoWorkflow, label: "Governed execution" },
] as const

/**
 * Technology / GIBE pilot page — Marketing System 4.0.
 * Signature visual: TRACE path (not generic Lucide orbit carnival).
 */
export function TechnologyPage() {
  return (
    <div className="bg-[color:var(--g-marketing-canvas)]">
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
          title="From knowledge to governed outcomes"
          description="One signature TRACE — how organizational intelligence moves through relationships and evidence before anything executes."
          className="mb-6"
        />
        <GravitreTrace>
          <GibeTraceVisual />
        </GravitreTrace>
      </GravitreSection>

      <DivideX />

      {/* Existing authorized GIBE/governance content — hero/tail suppressed */}
      <FeaturesLegacyContent section="intelligence" showHero={false} showTail={false} />
      <FeaturesLegacyContent section="governance" showHero={false} showTail={false} />

      <MarketingPageEndCta />
    </div>
  )
}
