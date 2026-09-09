import Link from "next/link"
import { Badge } from "@/components/marketing/nodus/badge"
import { Button } from "@/components/marketing/nodus/button"
import { Container } from "@/components/marketing/nodus/container"
import { CTA } from "@/components/marketing/nodus/cta"
import { DivideX } from "@/components/marketing/nodus/divide"
import { SectionHeading } from "@/components/marketing/nodus/seciton-heading"
import { SubHeading } from "@/components/marketing/nodus/subheading"
import {
  BoltIcon,
  CloudCheckIcon,
  HeartHandsIcon,
  ShieldSplitIcon,
  SparklesIcon,
  TelescopeIcon,
} from "@/components/marketing/nodus-icons/card-icons"
import {
  CAREERS_TRACE_STAGES,
  GravitreFlow,
  GravitreSection,
  GravitreSectionHeader,
  GravitreTrace,
  StageTraceVisual,
} from "@/components/marketing/system"

const howWeWork = [
  "Ownership — outcomes end to end",
  "Customer obsession — start with the problem",
  "Bias for action — ship, learn, iterate",
  "Default to open — share context",
]

const why = [
  {
    title: "Complete ownership",
    description: "Own outcomes end to end — from first sketch to production.",
    icon: <CloudCheckIcon className="text-brand size-6" />,
  },
  {
    title: "High-paced environment",
    description: "Ship quality at startup velocity with enterprise precision.",
    icon: <BoltIcon className="text-brand size-6" />,
  },
  {
    title: "Absolute integrity",
    description: "Transparency and honesty guide every decision.",
    icon: <ShieldSplitIcon className="text-brand size-6" />,
  },
  {
    title: "People-first culture",
    description: "Growth, well-being, and success are part of the mission.",
    icon: <HeartHandsIcon className="text-brand size-6" />,
  },
  {
    title: "Meaningful impact",
    description: "Build technology that changes how teams run their business.",
    icon: <SparklesIcon className="text-brand size-6" />,
  },
  {
    title: "Vision driven",
    description: "Help build one AI brain for the entire business.",
    icon: <TelescopeIcon className="text-brand size-4" />,
  },
]

/**
 * Careers — Nodus layout · Gravitre copy · Marketing System 4.0.
 * No fake investor / press logos, stock team photos, or invented openings.
 */
export default function CareersPage() {
  return (
    <main className="bg-[color:var(--g-marketing-canvas)]">
      <Container className="border-divide flex flex-col items-center border-x pb-16">
        <div className="divide-divide border-divide grid w-full grid-cols-1 border-b lg:grid-cols-2 lg:divide-x">
          <div className="flex flex-col items-start justify-start px-4 py-10 md:px-8 md:py-32">
            <Badge text="Careers" />
            <SectionHeading className="mt-4 text-left">
              Build one AI brain for business with us
            </SectionHeading>
            <SubHeading className="mt-6 mr-auto max-w-md text-left">
              Join a team working at the intersection of AI, automation, and
              enterprise software — with ownership, integrity, and customer focus.
            </SubHeading>
            <Button as={Link} href="#open-roles" className="mt-6">
              View roles
            </Button>
          </div>
          <div className="flex flex-col justify-center gap-4 px-4 py-10 md:px-8">
            <p className="font-mono text-xs tracking-tight text-neutral-500 uppercase">
              How we work
            </p>
            {howWeWork.map((line, i) => (
              <GravitreFlow key={line} delay={i * 0.06}>
                <p className="text-charcoal-700 text-sm font-medium md:text-base">{line}</p>
              </GravitreFlow>
            ))}
          </div>
        </div>
      </Container>

      <DivideX />

      <GravitreSection>
        <GravitreSectionHeader
          align="center"
          badge="Ownership path"
          title="Own → Ship → Learn → Impact"
          description="How we expect teammates to grow — end-to-end ownership, shipping with integrity, learning in public, and impact that compounds."
          className="mb-6"
        />
        <GravitreTrace>
          <StageTraceVisual
            stages={CAREERS_TRACE_STAGES}
            gradientId="careers-trace"
            ariaLabel="Careers path from Own through Ship and Learn to Impact"
          />
        </GravitreTrace>
      </GravitreSection>

      <DivideX />

      <div id="open-roles" className="scroll-mt-24">
        <Container className="border-divide flex flex-col items-center border-x border-b py-16 pb-20">
          <Badge text="Open Roles" />
          <SectionHeading className="mt-4 px-4 text-center">
            Open roles
          </SectionHeading>
          <SubHeading className="mx-auto mt-4 max-w-lg px-4 text-center">
            We are not listing invented openings. Reach out if you want to build with us.
          </SubHeading>
          <Button as={Link} href="/contact" className="mt-8">
            Contact careers
          </Button>
        </Container>
      </div>

      <Container className="border-divide flex flex-col items-center border-x border-b py-16 pb-20">
        <Badge text="Why Gravitre" />
        <SectionHeading className="mt-4 px-4 text-center">
          Why work at Gravitre?
        </SectionHeading>
        <div className="mt-12 grid grid-cols-1 gap-10 px-4 md:grid-cols-2 md:px-8 lg:grid-cols-3">
          {why.map((item) => (
            <div
              key={item.title}
              className="relative z-10 rounded-lg border border-divide bg-gray-50 p-4 transition duration-200 md:p-5"
            >
              <div className="flex items-center gap-2">{item.icon}</div>
              <h3 className="mt-4 mb-2 text-lg font-medium">{item.title}</h3>
              <p className="text-gray-600">{item.description}</p>
            </div>
          ))}
        </div>
      </Container>

      <CTA />
      <DivideX />
    </main>
  )
}
