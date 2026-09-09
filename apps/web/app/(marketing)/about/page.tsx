import Link from "next/link"
import { Badge } from "@/components/marketing/nodus/badge"
import { Button } from "@/components/marketing/nodus/button"
import { Container } from "@/components/marketing/nodus/container"
import { CTA } from "@/components/marketing/nodus/cta"
import { DivideX } from "@/components/marketing/nodus/divide"
import { Heading } from "@/components/marketing/nodus/heading"
import { SectionHeading } from "@/components/marketing/nodus/seciton-heading"
import { SubHeading } from "@/components/marketing/nodus/subheading"
import {
  ConvergeNodesVisual,
  GravitreSection,
  GravitreSectionHeader,
  GravitreTrace,
} from "@/components/marketing/system"
import { MARKETING_COPY } from "@/lib/marketing-copy"

/**
 * About — Nodus layout · Gravitre copy · Marketing System 4.0 converge signature.
 * No press logos, invented metrics, or placeholder founders.
 * Server component: ConvergeNodesVisual / GravitreTrace are client islands.
 */
export default function AboutPage() {
  const principles = MARKETING_COPY.about.principles

  return (
    <main className="bg-[color:var(--g-marketing-canvas)]">
      <Container className="border-divide flex flex-col items-center justify-center border-x px-4 pt-10 pb-10 md:px-8 md:pt-32 md:pb-20">
        <div className="grid w-full grid-cols-1 gap-12 md:grid-cols-2 md:gap-20">
          <div className="flex flex-col items-start justify-start">
            <Badge text="About Us" />
            <Heading className="mt-4 text-left">
              One AI brain for your entire business
            </Heading>
            <SubHeading className="mt-6 mr-auto text-left">
              Gravitre connects tools, teams, data, and processes so agents and
              workflows can automate work, measure what happened, and improve how
              the business runs — with human approval where it matters.
            </SubHeading>
            <Button as={Link} href="/get-started" className="mt-8">
              Put Gravitre to work
            </Button>
          </div>
          <div className="border-divide flex flex-col justify-center rounded-3xl border bg-gray-50 p-8 md:p-10">
            <p className="font-mono text-xs tracking-tight text-neutral-500 uppercase">
              What we believe
            </p>
            <p className="text-charcoal-700 mt-4 text-lg font-medium leading-relaxed">
              {MARKETING_COPY.homeNarrative.differentiation}
            </p>
            <p className="mt-6 text-sm text-gray-600">
              {MARKETING_COPY.homeNarrative.categoryLine}
            </p>
          </div>
        </div>
      </Container>

      <DivideX />

      <GravitreSection>
        <GravitreSectionHeader
          align="center"
          badge="One brain"
          title="Departments converge"
          description="Sales, support, ops, and finance feed the same governed intelligence — not four disconnected copilots."
          className="mb-6"
        />
        <GravitreTrace>
          <ConvergeNodesVisual />
        </GravitreTrace>
      </GravitreSection>

      <DivideX />

      <GravitreSection>
        <Badge text="Principles" />
        <SectionHeading className="mt-4 text-left md:text-center">
          How we build
        </SectionHeading>
        <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {principles.map((item, index) => (
            <div
              key={item.title}
              className="rounded-lg border border-divide bg-gray-50 p-5"
            >
              <p className="font-mono text-xs text-gray-500">
                {String(index + 1).padStart(2, "0")}
              </p>
              <h3 className="text-charcoal-700 mt-3 text-lg font-medium">{item.title}</h3>
              <p className="mt-2 text-sm text-gray-600">{item.description}</p>
            </div>
          ))}
        </div>
      </GravitreSection>

      <DivideX />

      <Container className="border-divide flex flex-col items-start border-x px-4 py-16 md:flex-row md:items-center md:justify-between md:px-8 md:py-20">
        <div>
          <Badge text="Careers" />
          <SectionHeading className="mt-4 text-left">
            Build with us
          </SectionHeading>
          <SubHeading className="mt-4 max-w-md text-left">
            Join the team working on one AI brain for business.
          </SubHeading>
        </div>
        <Button as={Link} href="/careers" className="mt-8 md:mt-0">
          View careers
        </Button>
      </Container>

      <CTA />
      <DivideX />
    </main>
  )
}
