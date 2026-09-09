"use client"

import Link from "next/link"
import {
  Search,
  BookOpen,
  MessageSquare,
  Mail,
  HelpCircle,
  Zap,
  Shield,
  Database,
  Users,
  CreditCard,
} from "lucide-react"
import { SUPPORT_CATEGORY_LINKS, SUPPORT_POPULAR_ARTICLES } from "@/lib/marketing-guide-links"
import { DivideX } from "@/components/marketing/nodus/divide"
import {
  MarketingPageEndCta,
  MarketingPageHero,
  MarketingRails,
} from "@/components/marketing/nodus/page-shell"
import {
  GravitreFlow,
  GravitreReveal,
  GravitreResolve,
  GravitreSection,
  GravitreSectionHeader,
  GravitreTrace,
  SUPPORT_TRACE_STAGES,
  StageTraceVisual,
} from "@/components/marketing/system"

const categories = [
  {
    icon: Zap,
    title: "Getting Started",
    description: "Setup guides and quickstarts",
    href: SUPPORT_CATEGORY_LINKS["Getting Started"],
  },
  {
    icon: Users,
    title: "Account & Billing",
    description: "Manage your subscription and team",
    href: SUPPORT_CATEGORY_LINKS["Account & Billing"],
  },
  {
    icon: Database,
    title: "Integrations",
    description: "Connect your tools and data",
    href: SUPPORT_CATEGORY_LINKS.Integrations,
  },
  {
    icon: Shield,
    title: "Security & Compliance",
    description: "Privacy, security, and compliance",
    href: SUPPORT_CATEGORY_LINKS["Security & Compliance"],
  },
  {
    icon: HelpCircle,
    title: "Troubleshooting",
    description: "Common issues and solutions",
    href: SUPPORT_CATEGORY_LINKS.Troubleshooting,
  },
  {
    icon: CreditCard,
    title: "API & Developers",
    description: "Technical documentation",
    href: SUPPORT_CATEGORY_LINKS["API & Developers"],
  },
]

const popularArticles = SUPPORT_POPULAR_ARTICLES

const faqs = [
  {
    question: "What is Gravitre?",
    answer:
      "Gravitre is one AI brain for your business — Gravitre AI, agents, workflows, connectors, approvals, and GIBE learning with human gates on writes.",
  },
  {
    question: "How do I get started?",
    answer:
      "Create an account, complete the onboarding wizard, and follow the getting-started guides to create your first agent and workflow.",
  },
  {
    question: "What integrations are supported?",
    answer:
      "Browse the integrations catalog in our docs for connectors we support today — including Salesforce, HubSpot, Slack, and more.",
  },
  {
    question: "Is my data secure?",
    answer:
      "Yes. Gravitre uses AES-256 encryption for all data at rest and in transit, with role-based access control and complete audit trails.",
  },
  {
    question: "Can I cancel anytime?",
    answer:
      "Yes, you can cancel your subscription at any time. Your access continues until the end of your current billing period.",
  },
]

export default function SupportPage() {
  return (
    <div className="bg-[color:var(--g-marketing-canvas)]">
      <MarketingPageHero
        badge="Support"
        title="How can we help?"
        description="Find answers, explore guides, and get support from our team."
      >
        <div className="mt-8 max-w-xl mx-auto w-full">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search for help..."
              className="w-full rounded-xl border border-border bg-card pl-12 pr-4 py-4 text-sm text-foreground placeholder:text-muted-foreground transition-colors focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
        </div>
      </MarketingPageHero>

      <DivideX />

      <GravitreSection>
        <GravitreSectionHeader
          align="center"
          badge="Support path"
          title="Find → Guide → Escalate → Resolve"
          description="Start self-service, follow the docs, then reach us when you need a human."
          className="mb-6"
        />
        <GravitreTrace>
          <StageTraceVisual
            stages={SUPPORT_TRACE_STAGES}
            gradientId="support-trace"
            ariaLabel="Support path from Find through Guide and Escalate to Resolve"
            caption="Calm escalation — docs first, then email or contact when guides aren't enough."
          />
        </GravitreTrace>
      </GravitreSection>

      <DivideX />

      <MarketingRails>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {categories.map((category, i) => {
            const Icon = category.icon
            return (
              <GravitreFlow
                key={category.title}
                delay={i * 0.08}
                className="group block rounded-xl border border-border bg-card p-6 transition-all hover:border-primary/30 hover:shadow-md"
              >
                <a href={category.href} className="block">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/15 mb-4">
                    <Icon className="h-5 w-5 text-primary" />
                  </div>
                  <h3 className="font-medium text-foreground group-hover:text-primary transition-colors">
                    {category.title}
                  </h3>
                  <p className="text-sm text-muted-foreground mt-1">{category.description}</p>
                </a>
              </GravitreFlow>
            )
          })}
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <div className="mx-auto max-w-3xl">
          <GravitreReveal className="mb-8">
            <h2 className="text-2xl font-semibold text-foreground">Popular articles</h2>
          </GravitreReveal>
          <div className="space-y-2">
            {popularArticles.map((article, i) => (
              <GravitreFlow
                key={article.title}
                delay={i * 0.05}
                className="block rounded-lg border border-border bg-card p-4 transition-all hover:border-border hover:shadow-sm"
              >
                <a href={article.href} className="flex items-center justify-between">
                  <span className="text-sm text-foreground">{article.title}</span>
                  <BookOpen className="h-4 w-4 text-muted-foreground" />
                </a>
              </GravitreFlow>
            ))}
          </div>
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <div className="mx-auto max-w-3xl">
          <GravitreReveal className="text-center mb-12">
            <h2 className="text-2xl font-semibold text-foreground mb-4">
              Frequently asked questions
            </h2>
          </GravitreReveal>
          <div className="space-y-4">
            {faqs.map((faq, i) => (
              <GravitreReveal key={faq.question} kind="focus" delay={i * 0.05}>
                <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
                  <h3 className="font-medium text-foreground mb-2">{faq.question}</h3>
                  <p className="text-sm text-muted-foreground">{faq.answer}</p>
                </div>
              </GravitreReveal>
            ))}
          </div>
        </div>
      </MarketingRails>

      <DivideX />

      <GravitreSection>
        <GravitreSectionHeader
          align="center"
          badge="Escalation path"
          title="Docs → Email → Chat"
          description="When self-service isn't enough, reach us through the channel that fits."
          className="mb-8"
        />
        <div className="grid gap-6 sm:grid-cols-3">
          <GravitreFlow className="group rounded-xl border border-border bg-card p-6 text-center transition-all hover:border-primary/30 hover:shadow-md">
            <Link href="/docs" className="block">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/15 mb-4">
                <BookOpen className="h-5 w-5 text-primary" />
              </div>
              <h3 className="font-medium text-foreground mb-1">Documentation</h3>
              <p className="text-sm text-muted-foreground">Guides, concepts, and API reference</p>
            </Link>
          </GravitreFlow>
          <GravitreFlow
            delay={0.1}
            className="group rounded-xl border border-border bg-card p-6 text-center transition-all hover:border-primary/30 hover:shadow-md"
          >
            <a href="mailto:support@gravitre.app" className="block">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/15 mb-4">
                <Mail className="h-5 w-5 text-primary" />
              </div>
              <h3 className="font-medium text-foreground mb-1">Email support</h3>
              <p className="text-sm text-muted-foreground">support@gravitre.app</p>
            </a>
          </GravitreFlow>
          <GravitreResolve
            delay={0.2}
            className="group rounded-xl border border-border bg-card p-6 text-center transition-all hover:border-primary/30 hover:shadow-md"
          >
            <Link href="/contact" className="block">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/15 mb-4">
                <MessageSquare className="h-5 w-5 text-primary" />
              </div>
              <h3 className="font-medium text-foreground mb-1">Contact</h3>
              <p className="text-sm text-muted-foreground">Send a message through our contact form</p>
            </Link>
          </GravitreResolve>
        </div>
      </GravitreSection>

      <MarketingPageEndCta />
    </div>
  )
}
