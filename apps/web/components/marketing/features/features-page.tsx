"use client"

import Link from "next/link"
import { useState } from "react"
import { motion } from "framer-motion"
import { AgenticIntelligence } from "@/components/marketing/nodus/agentic-intelligence"
import { Benefits } from "@/components/marketing/nodus/benefits"
import { Button } from "@/components/marketing/nodus/button"
import {
  Card,
  CardDescription,
  CardTitle,
} from "@/components/marketing/nodus/agentic-intelligence/card"
import { Container } from "@/components/marketing/nodus/container"
import { DivideX } from "@/components/marketing/nodus/divide"
import { HeroImage } from "@/components/marketing/nodus/hero-image"
import { HomeSecurityNote } from "@/components/marketing/nodus/home-security-note"
import { HowItWorks } from "@/components/marketing/nodus/how-it-works"
import {
  MarketingPageEndCta,
  MarketingPageHero,
} from "@/components/marketing/nodus/page-shell"
import { Badge } from "@/components/marketing/nodus/badge"
import { Scale } from "@/components/marketing/nodus/scale"
import { SectionHeading } from "@/components/marketing/nodus/seciton-heading"
import { SubHeading } from "@/components/marketing/nodus/subheading"
import {
  BrainIcon,
  FingerprintIcon,
  MouseBoxIcon,
  NativeIcon,
  RealtimeSyncIcon,
  SDKIcon,
} from "@/components/marketing/nodus-icons/bento-icons"
import { MARKETING_COPY } from "@/lib/marketing-copy"

const surfaceIcons = [
  BrainIcon,
  MouseBoxIcon,
  NativeIcon,
  FingerprintIcon,
  RealtimeSyncIcon,
  SDKIcon,
  BrainIcon,
] as const

/**
 * Features page — Nodus homepage chrome (divide rails, hero image, animated
 * how-it-works / agentic skeletons / benefits) with authorized Gravitre copy.
 * Legacy bento / muted-theme FeaturesLegacyContent is not used here.
 */
export function FeaturesPage() {
  const hero = MARKETING_COPY.featuresHero

  return (
    <main>
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
        <div className="mt-8 flex flex-wrap items-center justify-center gap-2.5">
          {hero.pills.map((pill) => (
            <span
              key={pill}
              className="rounded-full border border-divide bg-gray-50 px-3.5 py-2 text-sm font-medium text-charcoal-700"
            >
              {pill}
            </span>
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
      <HeroImage />
      <DivideX />
      <HowItWorks />
      <DivideX />
      <AgenticIntelligence />
      <DivideX />
      <ProductSurfaces />
      <DivideX />
      <AuthorizedUseCases />
      <DivideX />
      <HonestReporting />
      <DivideX />
      <Benefits />
      <DivideX />
      <HomeSecurityNote />
      <MarketingPageEndCta />
    </main>
  )
}

function ProductSurfaces() {
  const surfaces = MARKETING_COPY.homeFeatures

  return (
    <Container className="border-divide border-x">
      <div className="flex flex-col items-center py-16">
        <Badge text="Product surfaces" />
        <SectionHeading className="mt-4">
          Everything in the <span className="text-brand">same brain</span>
        </SectionHeading>
        <SubHeading as="p" className="mx-auto mt-6 max-w-lg px-2">
          Real Gravitre surfaces — chat, agents, workflows, connectors, approvals, and GIBE —
          not another disconnected AI silo.
        </SubHeading>
        <div className="border-divide divide-divide mt-16 grid w-full grid-cols-1 divide-y border-y md:grid-cols-2 md:divide-x lg:grid-cols-3">
          {surfaces.map((surface, index) => {
            const Icon = surfaceIcons[index % surfaceIcons.length]
            return (
              <Card key={surface.title} className="min-h-[180px]">
                <div className="flex items-center gap-2">
                  <Icon className="text-brand size-5 shrink-0" />
                  <CardTitle>{surface.title}</CardTitle>
                </div>
                <CardDescription>{surface.description}</CardDescription>
              </Card>
            )
          })}
        </div>
      </div>
    </Container>
  )
}

function AuthorizedUseCases() {
  const copy = MARKETING_COPY.useCases
  const [active, setActive] = useState<number | null>(null)

  return (
    <Container className="border-divide relative overflow-hidden border-x px-4 md:px-8">
      <div className="relative flex flex-col items-center py-20">
        <Badge text={copy.badge} />
        <SectionHeading className="mt-4">{copy.title}</SectionHeading>
        <SubHeading as="p" className="mx-auto mt-6 max-w-lg">
          {copy.subtitle}
        </SubHeading>

        <div className="mt-12 grid grid-cols-1 gap-10 md:grid-cols-2">
          {copy.cases.map((useCase, index) => (
            <div
              key={useCase.title}
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
                <h3 className="text-charcoal-700 mt-2 text-lg font-medium">{useCase.title}</h3>
                <p className="mt-2 text-sm text-gray-600 md:text-base">{useCase.description}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {useCase.surfaces.map((surface) => (
                    <span
                      key={surface}
                      className="rounded-full border border-divide bg-white px-2.5 py-1 text-xs font-medium text-gray-600"
                    >
                      {surface}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Container>
  )
}

function HonestReporting() {
  const copy = MARKETING_COPY.transparencyMetrics

  return (
    <Container className="border-divide border-x">
      <div className="flex flex-col items-center px-4 py-16 md:px-8">
        <Badge text={copy.badge} />
        <SectionHeading className="mt-4 text-center">{copy.title}</SectionHeading>
        <SubHeading as="p" className="mx-auto mt-6 max-w-lg">
          {copy.subtitle}
        </SubHeading>

        <div className="border-divide divide-divide mt-16 grid w-full grid-cols-1 divide-y border-y md:grid-cols-3 md:divide-x md:divide-y-0">
          {copy.tiers.map((tier) => (
            <Card key={tier.title}>
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
          ))}
        </div>

        <Link
          href={copy.blogLink.href}
          className="mt-10 text-sm font-medium text-brand underline-offset-4 hover:underline"
        >
          {copy.blogLink.label} →
        </Link>
      </div>
    </Container>
  )
}
