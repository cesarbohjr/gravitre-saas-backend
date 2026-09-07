"use client"

import React from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { Container } from "./container"
import { Badge } from "./badge"
import { SectionHeading } from "./seciton-heading"
import { DivideX } from "./divide"
import { Button } from "./button"
import { SlidingNumber } from "./sliding-number"
import { Scale } from "./scale"
import { CheckIcon } from "@/components/marketing/nodus-icons/card-icons"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { tiers, type PricingTier } from "@/lib/pricing-page-data"
import { usePricingAnnual } from "@/components/marketing/pricing/pricing-annual-context"

/**
 * Nodus pricing chrome with authorized Gravitre plans only.
 * Prices / features come from `@/lib/pricing-page-data` (PLAN_CATALOG) — never template demo dollars.
 */
export function Pricing() {
  const { isAnnual, setIsAnnual } = usePricingAnnual()
  const cycle = isAnnual ? "yearly" : "monthly"

  const tabs = [
    { title: "Monthly", value: "monthly" as const, badge: "" },
    { title: "Yearly", value: "yearly" as const, badge: "2 months free" },
  ]

  return (
    <section>
      <Container className="border-divide flex flex-col items-center justify-center border-x px-4 pt-10 pb-10 md:px-8">
        <Badge text="Pricing" />
        <SectionHeading className="mt-4">
          {MARKETING_COPY.pricing.headline[0]}{" "}
          <span className="text-brand">{MARKETING_COPY.pricing.headline[1]}</span>
        </SectionHeading>
        <p className="mt-4 max-w-2xl text-center text-base font-medium tracking-tight text-gray-600 md:text-lg dark:text-neutral-400">
          {MARKETING_COPY.pricing.subhead}
        </p>
        <p className="mt-2 text-center text-sm text-gray-600 dark:text-neutral-500">
          {MARKETING_COPY.pricing.subheadNote}
        </p>

        <div className="relative mt-8 flex items-center gap-4 rounded-xl bg-gray-50 p-2 dark:bg-neutral-800">
          <Scale className="opacity-50" />
          {tabs.map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => setIsAnnual(tab.value === "yearly")}
              className="relative z-20 flex w-32 justify-center py-1 text-center sm:w-40"
            >
              {cycle === tab.value && (
                <motion.div
                  layoutId="pricing-active-span"
                  className="shadow-aceternity absolute inset-0 h-full w-full rounded-md bg-white dark:bg-neutral-950"
                />
              )}
              <span className="relative z-20 flex items-center gap-2 text-sm sm:text-base">
                {tab.title}{" "}
                {tab.badge ? (
                  <span className="bg-brand/10 text-brand rounded-full px-2 py-1 text-xs font-medium">
                    {tab.badge}
                  </span>
                ) : null}
              </span>
            </button>
          ))}
        </div>
        <p className="mt-3 text-xs text-gray-500 dark:text-neutral-500">
          {isAnnual
            ? "Annual billing — per-month equivalent shown (billed yearly)"
            : "Prices in USD · billed monthly"}
        </p>
      </Container>

      <DivideX />

      <Container className="border-divide border-x">
        <div className="divide-divide grid grid-cols-1 divide-y md:grid-cols-3 md:divide-x md:divide-y-0">
          {tiers.map((tier) => (
            <TierMeta key={tier.name} tier={tier} isAnnual={isAnnual} />
          ))}
        </div>
      </Container>

      <DivideX />

      <Container className="border-divide hidden border-x md:block">
        <div className="divide-divide grid grid-cols-1 md:grid-cols-3 md:divide-x">
          {tiers.map((tier) => (
            <div key={`${tier.name}-features`} className="flex flex-col gap-4 p-4 md:p-8">
              {tierFeatureLines(tier).map((feature) => (
                <Step key={feature}>{feature}</Step>
              ))}
            </div>
          ))}
        </div>
      </Container>
    </section>
  )
}

function tierFeatureLines(tier: PricingTier): string[] {
  const lines = [
    tier.team.agents,
    tier.team.coreUsers,
    tier.team.liteUsers,
    tier.outputs,
    ...(tier.meson ? [tier.meson.label] : []),
    ...tier.features,
  ]
  return lines
}

function TierMeta({ tier, isAnnual }: { tier: PricingTier; isAnnual: boolean }) {
  const price = isAnnual ? tier.price.annual : tier.price.monthly
  const href = `/get-started?plan=${tier.planCode}&interval=${isAnnual ? "annual" : "monthly"}`

  return (
    <div className="p-4 md:p-8">
      <div className="flex items-center gap-2">
        <h3 className="text-charcoal-700 text-xl font-medium dark:text-neutral-100">{tier.name}</h3>
        {"badge" in tier && tier.badge ? (
          <span className="bg-brand/10 text-brand rounded-full px-2 py-0.5 text-xs font-medium">
            {tier.badge}
          </span>
        ) : null}
      </div>
      <p className="mt-1 text-base text-gray-600 dark:text-neutral-400">{tier.tagline}</p>
      <p className="mt-3 text-sm leading-relaxed text-gray-500 dark:text-neutral-500">{tier.description}</p>

      <span className="mt-6 flex items-baseline text-2xl font-medium dark:text-white">
        $<SlidingNumber value={price} />
        <span className="ml-2 text-sm font-normal text-gray-600 dark:text-neutral-400">/month</span>
      </span>
      {isAnnual ? (
        <p className="mt-1 text-xs text-brand">
          Billed annually (save ${(tier.price.monthly - tier.price.annual) * 12}/year)
        </p>
      ) : null}

      <div className="mt-4 flex flex-col gap-4 md:hidden">
        {tierFeatureLines(tier).map((feature) => (
          <Step key={feature}>{feature}</Step>
        ))}
      </div>

      <Button
        className="mt-6 w-full"
        as={Link}
        href={href}
        variant={tier.highlighted ? "brand" : "secondary"}
      >
        {tier.cta}
      </Button>
    </div>
  )
}

function Step({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-charcoal-700 flex items-start gap-2 text-sm dark:text-neutral-100">
      <CheckIcon className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{children}</span>
    </div>
  )
}
