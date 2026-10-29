"use client";

import Link from "next/link";
import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Button } from "@/components/marketing/nodus/button";
import {
  Card,
  CardDescription,
  CardTitle,
} from "@/components/marketing/nodus/agentic-intelligence/card";
import { Container } from "@/components/marketing/nodus/container";
import { DivideX } from "@/components/marketing/nodus/divide";
import { HeroImage } from "@/components/marketing/nodus/hero-image";
import { ProductScreenshot } from "@/components/marketing/product-screenshot";
import {
  MarketingPageEndCta,
  MarketingPageHero,
} from "@/components/marketing/nodus/page-shell";
import { Badge } from "@/components/marketing/nodus/badge";
import { Scale } from "@/components/marketing/nodus/scale";
import { SectionHeading } from "@/components/marketing/nodus/seciton-heading";
import { SubHeading } from "@/components/marketing/nodus/subheading";
import {
  BrainIcon,
  FingerprintIcon,
  MouseBoxIcon,
  NativeIcon,
  RealtimeSyncIcon,
  SDKIcon,
} from "@/components/marketing/nodus-icons/bento-icons";
import {
  FEATURES_TRACE_STAGES,
  GravitreFlow,
  GravitreReveal,
  GravitreSection,
  GravitreSectionHeader,
  GravitreTrace,
  StageTraceVisual,
} from "@/components/marketing/system";
import { MARKETING_COPY } from "@/lib/marketing-copy";

/** Hero pill → the real app screen it names (captures from /e2e/shots). */
const HERO_SHOTS: Record<
  string,
  { src: string; alt: string; width: number; height: number; title: string }
> = {
  "Gravitre AI": {
    src: "/product/app-ai.png",
    alt: "Gravitre AI chat: ask, delegate, or search across your connected stack",
    width: 2880,
    height: 1800,
    title: "Gravitre AI",
  },
  Agents: {
    src: "/product/app-agents-team.png",
    alt: "Gravitre Agents: your AI workforce by department",
    width: 2880,
    height: 1620,
    title: "Agents",
  },
  Workflows: {
    src: "/product/app-workflows.png",
    alt: "Gravitre Workflows: status, runs and failure signals across connectors",
    width: 2880,
    height: 1800,
    title: "Workflows",
  },
  Connectors: {
    src: "/product/app-connectors-hub.png",
    alt: "Gravitre Connectors: each system from connected to ready for agents",
    width: 2880,
    height: 1620,
    title: "Connectors",
  },
  Approvals: {
    src: "/product/app-approvals.png",
    alt: "Gravitre decision queue with a paused write waiting for approval",
    width: 2880,
    height: 1800,
    title: "Approvals",
  },
  GIBE: {
    src: "/product/app-knowledge.png",
    alt: "Gravitre Knowledge: what GIBE has learned about how your business connects",
    width: 2880,
    height: 1800,
    title: "Knowledge",
  },
};

const surfaceIcons = [
  BrainIcon,
  MouseBoxIcon,
  NativeIcon,
  FingerprintIcon,
  RealtimeSyncIcon,
  SDKIcon,
  BrainIcon,
] as const;

/**
 * Features page — Marketing System 4.0.
 * Distinct from home: Coordinate → Act → Approve → Resolve TRACE, not a homepage clone.
 */
export function FeaturesPage() {
  const hero = MARKETING_COPY.featuresHero;
  const [activePill, setActivePill] = useState<string>("Agents");
  const shot = HERO_SHOTS[activePill] ?? HERO_SHOTS.Agents;
  // Auto-tour the screens; hovering the pills or the window pauses it.
  const reduceMotion = useReducedMotion();
  const [paused, setPaused] = useState(false);
  const autoplay = !reduceMotion && !paused;
  const nextPill = () => {
    const pills: readonly string[] = hero.pills;
    const i = pills.indexOf(activePill);
    setActivePill(pills[(i + 1) % pills.length]);
  };

  return (
    <main className="bg-[color:var(--g-marketing-canvas)]">
      <MarketingPageHero
        badge={hero.badge}
        title={
          <>
            {hero.headline[0]}{" "}
            <span className="text-brand">{hero.headline[1]}</span>
          </>
        }
        description={hero.subtitle}
      >
        <div
          className="mt-8 flex flex-wrap items-center justify-center gap-2.5"
          onMouseEnter={() => setPaused(true)}
          onMouseLeave={() => setPaused(false)}
        >
          {hero.pills.map((pill) => (
            <button
              key={pill}
              type="button"
              onClick={() => setActivePill(pill)}
              aria-pressed={activePill === pill}
              className={
                activePill === pill
                  ? "relative overflow-hidden rounded-full border border-charcoal-900 bg-charcoal-900 px-3.5 py-2 text-sm font-medium text-background transition-colors"
                  : "relative overflow-hidden rounded-full border border-divide bg-[color:var(--g-marketing-surface)] px-3.5 py-2 text-sm font-medium text-charcoal-700 transition-colors hover:text-charcoal-900"
              }
            >
              {pill}
              {activePill === pill && autoplay ? (
                <motion.span
                  key={pill}
                  aria-hidden
                  className="absolute inset-x-0 bottom-0 h-[2px] origin-left bg-brand"
                  initial={{ scaleX: 0 }}
                  animate={{ scaleX: 1 }}
                  transition={{ duration: 5, ease: "linear" }}
                  onAnimationComplete={nextPill}
                />
              ) : null}
            </button>
          ))}
        </div>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Button as={Link} href="/get-started">
            Put Gravitre to work
          </Button>
          <Button as={Link} href="/pricing" variant="secondary">
            View pricing
          </Button>
        </div>
      </MarketingPageHero>

      <DivideX />
      <div
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
      >
        <HeroImage
          animateKey={shot.src}
          src={shot.src}
          alt={shot.alt}
          width={shot.width}
          height={shot.height}
          title={shot.title}
          chips={[
            {
              label: "Human approval on writes",
              at: "bottom-right",
              tone: "amber",
            },
          ]}
        />
      </div>
      <DivideX />

      <GravitreSection>
        <GravitreSectionHeader
          align="center"
          badge="Agent path"
          title="Coordinate → Act → Approve → Resolve"
          description="How agents move work through Gravitre — distinct from the homepage story spine."
          className="mb-6"
        />
        <GravitreTrace>
          <StageTraceVisual
            stages={FEATURES_TRACE_STAGES}
            gradientId="features-trace"
            ariaLabel="Features path from coordinate through act and approve to resolve"
            caption="Agents coordinate, act, clear approvals, then resolve — same gates as chat and workflows."
          />
        </GravitreTrace>
      </GravitreSection>

      <DivideX />

      <GravitreSection>
        <GravitreSectionHeader
          align="center"
          badge="Voice path"
          title="Waveform to response — same brain as chat"
          description="Talk to Gravitre from the desktop app: tap the orb or use the push-to-talk shortcut from any app, and it answers out loud with a live transcript saved to the conversation."
          className="mb-6"
        />
        <ProductScreenshot
          src="/product/desktop-voice.png"
          alt="Gravitre desktop voice mode: the orb speaking an answer, with the live transcript beside it"
          width={2360}
          height={1280}
          chromeLabel="Gravitre Desktop · Voice"
          className="mx-auto max-w-4xl"
        />
      </GravitreSection>

      <DivideX />
      <ProductSurfaces />
      <DivideX />
      <AuthorizedUseCases />
      <DivideX />
      <HonestReporting />
      <MarketingPageEndCta />
    </main>
  );
}

function ProductSurfaces() {
  const surfaces = MARKETING_COPY.homeFeatures;

  return (
    <Container className="border-divide md:border-x">
      <div className="flex flex-col items-center py-16">
        <GravitreReveal>
          <Badge text="Surfaces" />
          <SectionHeading className="mt-4">
            Everything in the <span className="text-brand">same brain</span>
          </SectionHeading>
          <SubHeading as="p" className="mx-auto mt-6 max-w-lg px-2">
            Real Gravitre surfaces — chat, agents, workflows, connectors,
            approvals, and GIBE — not another disconnected AI silo.
          </SubHeading>
        </GravitreReveal>
        <div className="border-divide divide-divide mt-16 grid w-full grid-cols-1 divide-y border-y md:grid-cols-2 md:divide-x lg:grid-cols-3">
          {surfaces.map((surface, index) => {
            const Icon = surfaceIcons[index % surfaceIcons.length];
            return (
              <GravitreFlow key={surface.title} delay={index * 0.05}>
                <Card className="min-h-[180px]">
                  <div className="flex items-center gap-2">
                    <Icon className="text-brand size-5 shrink-0" />
                    <CardTitle>{surface.title}</CardTitle>
                  </div>
                  <CardDescription>{surface.description}</CardDescription>
                </Card>
              </GravitreFlow>
            );
          })}
        </div>
      </div>
    </Container>
  );
}

function AuthorizedUseCases() {
  const copy = MARKETING_COPY.useCases;
  const [active, setActive] = useState<number | null>(null);

  return (
    <Container className="border-divide relative overflow-hidden md:border-x px-4 md:px-8">
      <div className="relative flex flex-col items-center py-20">
        <GravitreReveal>
          <Badge text={copy.badge} />
          <SectionHeading className="mt-4">{copy.title}</SectionHeading>
          <SubHeading as="p" className="mx-auto mt-6 max-w-lg">
            {copy.subtitle}
          </SubHeading>
        </GravitreReveal>

        <div className="mt-12 grid grid-cols-1 gap-10 md:grid-cols-2">
          {copy.cases.map((useCase, index) => (
            <GravitreFlow
              key={useCase.title}
              delay={index * 0.06}
              onMouseEnter={() => setActive(index)}
              onMouseLeave={() => setActive(null)}
              className="relative"
            >
              {active === index ? (
                <motion.div
                  layoutId="features-use-case-scale"
                  className="absolute inset-0 z-0"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 0.5 }}
                  exit={{ opacity: 0 }}
                >
                  <Scale />
                </motion.div>
              ) : null}
              <div className="relative z-10 p-4 md:p-6">
                <p className="text-brand text-xs font-medium tracking-wide uppercase">
                  {useCase.department}
                </p>
                <h3 className="text-charcoal-700 mt-2 text-lg font-medium">
                  {useCase.title}
                </h3>
                <p className="mt-2 text-sm text-gray-600 md:text-base">
                  {useCase.description}
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {useCase.surfaces.map((surface) => (
                    <span
                      key={surface}
                      className="rounded-full border border-divide bg-card px-2.5 py-1 text-xs font-medium text-gray-600"
                    >
                      {surface}
                    </span>
                  ))}
                </div>
              </div>
            </GravitreFlow>
          ))}
        </div>
      </div>
    </Container>
  );
}

function HonestReporting() {
  const copy = MARKETING_COPY.transparencyMetrics;

  return (
    <Container className="border-divide md:border-x">
      <div className="flex flex-col items-center px-4 py-16 md:px-8">
        <GravitreReveal>
          <Badge text={copy.badge} />
          <SectionHeading className="mt-4 text-center">
            {copy.title}
          </SectionHeading>
          <SubHeading as="p" className="mx-auto mt-6 max-w-lg">
            {copy.subtitle}
          </SubHeading>
        </GravitreReveal>

        <div className="border-divide divide-divide mt-16 grid w-full grid-cols-1 divide-y border-y md:grid-cols-3 md:divide-x md:divide-y-0">
          {copy.tiers.map((tier, i) => (
            <GravitreFlow key={tier.title} delay={i * 0.08}>
              <Card>
                <CardTitle>{tier.title}</CardTitle>
                <CardDescription>{tier.description}</CardDescription>
                <ul className="mt-4 space-y-2">
                  {tier.examples.map((example) => (
                    <li key={example} className="text-sm text-gray-600">
                      · {example}
                    </li>
                  ))}
                </ul>
              </Card>
            </GravitreFlow>
          ))}
        </div>

        <GravitreReveal delay={0.1}>
          <Link
            href={copy.blogLink.href}
            className="mt-10 text-sm font-medium text-brand underline-offset-4 hover:underline"
          >
            {copy.blogLink.label} →
          </Link>
        </GravitreReveal>
      </div>
    </Container>
  );
}
