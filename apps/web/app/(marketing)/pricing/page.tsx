import Link from "next/link"
import {
  Check,
  FileText,
  Monitor,
  Smartphone,
  Crown,
  Users,
} from "lucide-react"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { addOns, howItWorks, roles } from "@/lib/pricing-page-data"
import { PricingAnnualProvider } from "@/components/marketing/pricing/pricing-annual-context"
import { PricingFaqAccordion } from "@/components/marketing/pricing/pricing-faq-accordion"
import { Pricing } from "@/components/marketing/nodus/pricing"
import { PricingTable } from "@/components/marketing/nodus/pricing-table"
import { Container } from "@/components/marketing/nodus/container"
import { DivideX } from "@/components/marketing/nodus/divide"
import { Badge } from "@/components/marketing/nodus/badge"
import { SectionHeading } from "@/components/marketing/nodus/seciton-heading"
import { Button } from "@/components/marketing/nodus/button"
import { MarketingPageEndCta } from "@/components/marketing/nodus/page-shell"
import { CheckIcon } from "@/components/marketing/nodus-icons/card-icons"

/**
 * /pricing — Nodus theme chrome + authorized Gravitre plans only.
 * (a) Explicitly requested Nodus visual parity; prices/features from PLAN_CATALOG.
 */
export default function PricingPage() {
  return (
    <PricingAnnualProvider>
      <div className="relative overflow-hidden bg-white dark:bg-neutral-950">
        <Pricing />

        <DivideX />

        {/* Roles — Nodus rail */}
        <Container className="border-divide border-x px-4 py-12 md:px-8 md:py-16">
          <div className="mb-8 flex items-center gap-2">
            <Users className="h-5 w-5 text-gray-500" />
            <h3 className="text-charcoal-700 text-lg font-medium dark:text-neutral-100">
              How teams use Gravitre
            </h3>
          </div>
          <div className="divide-divide grid grid-cols-1 divide-y md:grid-cols-3 md:divide-x md:divide-y-0">
            {[
              {
                icon: Monitor,
                title: roles.coreUser.name,
                eyebrow: "Gravitre Core",
                body: "Build and configure agents, create workflows, and manage outputs. Full access to the desktop experience.",
              },
              {
                icon: Smartphone,
                title: roles.liteUser.name,
                eyebrow: "Gravitre Lite",
                body: "Assign work and view outputs on mobile. Perfect for team-wide adoption without the learning curve.",
              },
              {
                icon: Crown,
                title: roles.masterAdmin.name,
                eyebrow: "Included",
                body: "Full system control, billing management, and organization settings. One per account.",
              },
            ].map((role) => (
              <div key={role.title} className="p-4 md:p-6">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand/10 text-brand">
                    <role.icon className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-charcoal-700 font-medium dark:text-neutral-100">{role.title}</p>
                    <p className="text-xs text-gray-500">{role.eyebrow}</p>
                  </div>
                </div>
                <p className="mt-3 text-sm leading-relaxed text-gray-600 dark:text-neutral-400">{role.body}</p>
              </div>
            ))}
          </div>
        </Container>

        <DivideX />

        {/* Add-ons */}
        <Container className="border-divide border-x px-4 py-12 md:px-8 md:py-16">
          <h3 className="text-charcoal-700 text-lg font-medium dark:text-neutral-100">Need more?</h3>
          <div className="divide-divide mt-6 grid grid-cols-1 divide-y sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-4">
            {addOns.map((addon) => {
              const AddonIcon = addon.icon
              return (
                <div key={addon.name} className="p-4 md:p-6">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gray-100 text-gray-600 dark:bg-neutral-800 dark:text-neutral-300">
                    <AddonIcon className="h-4 w-4" />
                  </div>
                  <p className="text-charcoal-700 mt-3 font-medium dark:text-neutral-100">{addon.name}</p>
                  <p className="text-brand mt-1 text-sm font-medium">{addon.price}</p>
                  <p className="mt-2 text-sm text-gray-600 dark:text-neutral-400">{addon.description}</p>
                </div>
              )
            })}
          </div>
          <div className="border-divide mt-10 border-t pt-10 text-center">
            <h3 className="text-charcoal-700 text-xl font-medium dark:text-neutral-100">
              Need enterprise scale?
            </h3>
            <p className="mx-auto mt-2 max-w-lg text-sm text-gray-600 dark:text-neutral-400">
              Custom agent counts, SLAs, dedicated infrastructure, and white-glove onboarding.
            </p>
            <Button as={Link} href="/contact" variant="secondary" className="mt-6">
              Talk to Sales
            </Button>
          </div>
        </Container>

        <DivideX />

        {/* Meson — authorized capability, Nodus chrome */}
        <Container className="border-divide border-x px-4 py-12 md:px-8 md:py-16">
          <div className="mx-auto max-w-3xl text-center">
            <Badge text="System Builder" />
            <SectionHeading className="mt-4">Build your system with Meson</SectionHeading>
            <p className="mt-3 text-base text-gray-600 dark:text-neutral-400">
              Meson creates agents, training, and workflows from a single request.
            </p>
          </div>
          <div className="divide-divide mt-10 grid grid-cols-1 divide-y md:grid-cols-2 md:divide-x md:divide-y-0">
            <div className="p-6 text-center md:p-8">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-gray-100 dark:bg-neutral-800">
                <FileText className="h-5 w-5 text-gray-600 dark:text-neutral-300" />
              </div>
              <h3 className="text-charcoal-700 font-medium dark:text-neutral-100">Describe what you need</h3>
              <p className="mt-2 text-sm text-gray-600 dark:text-neutral-400">
                {'"Create a marketing agent for SaaS onboarding campaigns"'}
              </p>
            </div>
            <div className="p-6 text-center md:p-8">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-brand/10">
                <Check className="h-5 w-5 text-brand" />
              </div>
              <h3 className="text-charcoal-700 font-medium dark:text-neutral-100">Meson generates</h3>
              <p className="mt-2 text-sm text-gray-600 dark:text-neutral-400">
                Agent config, training structure, workflows, sample outputs
              </p>
            </div>
          </div>
          <p className="mt-8 text-center text-sm text-gray-500">
            Meson builds the system. Gravitre executes it. Available on Control and Command.
          </p>
        </Container>

        <DivideX />

        {/* Value pillars */}
        <Container className="border-divide border-x px-4 py-12 md:px-8 md:py-16">
          <SectionHeading>Not another AI silo. One shared brain.</SectionHeading>
          <div className="divide-divide mt-10 grid grid-cols-1 divide-y sm:grid-cols-2 sm:divide-x sm:divide-y-0">
            {[
              {
                title: "Complete work, not suggestions",
                description:
                  "Gravitre AI and workflows execute through connected tools — with live Configured → Executable checks before writes.",
              },
              {
                title: "Measured outcomes, not theater",
                description:
                  "Runs, approvals, and connector actions leave audit trails. Dollar ROI stays blank until your org measures it.",
              },
              {
                title: "Delivered into your stack",
                description:
                  "Outputs land in the systems you connect — CRM, email, Slack, and more — when those connectors are healthy and executable.",
              },
              {
                title: "Learns from verified signals",
                description:
                  "GIBE promotes memories and trains rankers only when data gates pass — honest TRAINED / not-ready status, not fake green checks.",
              },
            ].map((item) => (
              <div key={item.title} className="p-4 md:p-6">
                <h3 className="text-charcoal-700 font-medium dark:text-neutral-100">{item.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-gray-600 dark:text-neutral-400">
                  {item.description}
                </p>
              </div>
            ))}
          </div>
        </Container>

        <DivideX />

        {/* How it works */}
        <Container className="border-divide border-x px-4 py-12 md:px-8 md:py-16">
          <div className="text-center">
            <Badge text="How it works" />
            <SectionHeading className="mt-4">From request to delivery</SectionHeading>
          </div>
          <div className="divide-divide mt-10 grid grid-cols-1 divide-y sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-4 lg:divide-y-0">
            {howItWorks.map((item) => (
              <div key={item.step} className="p-4 md:p-6">
                <div className="mb-3 flex items-center gap-2">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gray-100 dark:bg-neutral-800">
                    <item.icon className="h-4 w-4 text-gray-600 dark:text-neutral-300" />
                  </div>
                  <span className="text-xs font-mono text-gray-500">{item.step}</span>
                </div>
                <h3 className="text-charcoal-700 font-medium dark:text-neutral-100">{item.title}</h3>
                <p className="mt-2 text-sm text-gray-600 dark:text-neutral-400">{item.description}</p>
              </div>
            ))}
          </div>
        </Container>

        <DivideX />

        <PricingTable />

        <DivideX />

        {/* Trust strip */}
        <Container className="border-divide border-x px-4 py-10 md:px-8">
          <div className="divide-divide grid grid-cols-1 divide-y sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-4 lg:divide-y-0">
            {[
              { title: "Enterprise-grade security", description: "End-to-end encryption" },
              { title: "7-day free trial", description: "Full access to plan features" },
              { title: "Cancel anytime", description: "No long-term contracts" },
              { title: "Money-back guarantee", description: "30-day refund policy" },
            ].map((item) => (
              <div key={item.title} className="flex items-start gap-3 p-4 md:p-6">
                <CheckIcon className="mt-0.5 h-4 w-4 shrink-0" />
                <div>
                  <p className="text-charcoal-700 text-sm font-medium dark:text-neutral-100">{item.title}</p>
                  <p className="text-xs text-gray-500">{item.description}</p>
                </div>
              </div>
            ))}
          </div>
        </Container>

        <DivideX />

        {/* FAQ */}
        <Container className="border-divide border-x px-4 py-12 md:px-8 md:py-16">
          <div className="mx-auto max-w-3xl">
            <div className="mb-10 text-center">
              <Badge text="FAQs" />
              <SectionHeading className="mt-4">Frequently asked questions</SectionHeading>
            </div>
            <PricingFaqAccordion />
          </div>
        </Container>

        <DivideX />

        {/* Final CTA — Nodus end CTA */}
        <Container className="border-divide flex flex-col items-center border-x px-4 py-16 text-center md:px-8 md:py-24">
          <SectionHeading>{MARKETING_COPY.pricing.cta.title}</SectionHeading>
          <p className="mt-4 max-w-xl text-base text-gray-600 dark:text-neutral-400">
            {MARKETING_COPY.pricing.cta.subtitle}
          </p>
          <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row">
            <Button as={Link} href="/get-started" variant="primary">
              Start your 7-day free trial
            </Button>
            <Button as={Link} href="/get-started" variant="secondary">
              Start free — no card required
            </Button>
          </div>
          <p className="mt-4 text-sm text-gray-500">Full access for 7 days. Cancel anytime.</p>
        </Container>

        <MarketingPageEndCta />
      </div>
    </PricingAnnualProvider>
  )
}
