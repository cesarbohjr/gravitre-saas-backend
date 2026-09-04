import Link from "next/link"
import {
  ArrowRight,
  BadgeCheck,
  Blocks,
  Check,
  Clock,
  Crown,
  FileText,
  HelpCircle,
  Info,
  Minus,
  Monitor,
  RefreshCcw,
  Shield,
  Smartphone,
  Sparkles,
  Star,
  Users,
} from "lucide-react"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { SHOW_MARKETING_TESTIMONIALS, SHOW_RESEARCH_LOOKUPS_PRICING } from "@/lib/marketing-flags"
import {
  addOns,
  aiCapabilityRows,
  howItWorks,
  type PlanComparisonCell,
} from "@/lib/pricing-page-data"
import { PricingAnnualProvider } from "@/components/marketing/pricing/pricing-annual-context"
import { PricingBillingToggle } from "@/components/marketing/pricing/pricing-billing-toggle"
import { PricingCardsGrid } from "@/components/marketing/pricing/pricing-cards-grid"
import { PricingComparisonPrices } from "@/components/marketing/pricing/pricing-comparison-prices"
import { PricingFaqAccordion } from "@/components/marketing/pricing/pricing-faq-accordion"

function renderPlanComparisonCell(value: PlanComparisonCell, tier: "node" | "control" | "command") {
  if (typeof value === "boolean") {
    return value ? (
      <div className="h-6 w-6 rounded-full bg-primary/15 flex items-center justify-center">
        <Check className="h-4 w-4 text-primary" />
      </div>
    ) : (
      <div className="h-6 w-6 rounded-full bg-muted flex items-center justify-center">
        <Minus className="h-4 w-4 text-muted-foreground" />
      </div>
    )
  }

  const className =
    tier === "node"
      ? "inline-flex items-center justify-center px-2 py-1 rounded-full bg-muted text-sm font-semibold text-foreground"
      : tier === "control"
        ? "inline-flex items-center justify-center px-2 py-1 rounded-full bg-amber-100 text-sm font-semibold text-amber-700"
        : "inline-flex items-center justify-center px-2 py-1 rounded-full bg-primary/15 text-sm font-semibold text-primary"

  return <span className={className}>{value}</span>
}

export default function PricingPage() {
  return (
    <PricingAnnualProvider>
      <div className="relative overflow-hidden bg-card">
        {/* Hero */}
        <section className="relative py-24 sm:py-32 overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-b from-amber-50 via-transparent to-transparent" />
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-amber-100/30 rounded-full blur-3xl" />

          <div className="relative mx-auto max-w-7xl px-6">
            <div className="mx-auto max-w-3xl text-center">
              <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50/80 backdrop-blur-sm px-4 py-2">
                <div className="h-2 w-2 rounded-full bg-amber-500" />
                <span className="text-sm font-medium text-amber-700">{MARKETING_COPY.pricing.badge}</span>
              </div>

              <div className="overflow-hidden">
                <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight">
                  <span className="text-foreground">{MARKETING_COPY.pricing.headline[0]}</span>
                </h1>
              </div>
              <div className="overflow-hidden">
                <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight">
                  <span className="bg-gradient-to-r from-amber-600 to-orange-500 bg-clip-text text-transparent">
                    {MARKETING_COPY.pricing.headline[1]}
                  </span>
                </h1>
              </div>

              <p className="mt-6 text-lg text-muted-foreground leading-relaxed">{MARKETING_COPY.pricing.subhead}</p>
              <p className="mt-3 text-sm text-muted-foreground">{MARKETING_COPY.pricing.subheadNote}</p>

              <div className="mt-6">
                <Link
                  href="/get-started"
                  className="group inline-flex items-center gap-2 rounded-full border border-border bg-card px-6 py-3 text-sm font-semibold text-foreground transition-all hover:bg-muted/50 hover:border-border"
                >
                  Start free — no card required
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                </Link>
              </div>

              <PricingBillingToggle />
            </div>
          </div>
        </section>

        {/* Role Explanation Section */}
        <section className="relative pb-16">
          <div className="mx-auto max-w-7xl px-6">
            <div className="rounded-2xl border border-border bg-card p-6 sm:p-8 shadow-sm">
              <div className="flex items-center gap-2 mb-6">
                <Users className="h-5 w-5 text-muted-foreground" />
                <h3 className="text-lg font-semibold text-foreground">How teams use Gravitre</h3>
              </div>

              <div className="grid sm:grid-cols-3 gap-6">
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-xl bg-blue-100 flex items-center justify-center">
                      <Monitor className="h-5 w-5 text-blue-600" />
                    </div>
                    <div>
                      <p className="font-medium text-foreground">Core Users</p>
                      <p className="text-xs text-muted-foreground">Gravitre Core</p>
                    </div>
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    Build and configure agents, create workflows, and manage outputs. Full access to the desktop experience.
                  </p>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-xl bg-primary/15 flex items-center justify-center">
                      <Smartphone className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <p className="font-medium text-foreground">Lite Users</p>
                      <p className="text-xs text-muted-foreground">Gravitre Lite</p>
                    </div>
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    Assign work and view outputs on mobile. Perfect for team-wide adoption without the learning curve.
                  </p>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-xl bg-amber-100 flex items-center justify-center">
                      <Crown className="h-5 w-5 text-amber-600" />
                    </div>
                    <div>
                      <p className="font-medium text-foreground">Master Admin</p>
                      <p className="text-xs text-muted-foreground">Included</p>
                    </div>
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    Full system control, billing management, and organization settings. One per account.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Pricing Cards */}
        <section className="relative pb-16 sm:pb-24">
          <div className="mx-auto max-w-7xl px-4 sm:px-6">
            <PricingCardsGrid />

            <div className="mt-12 rounded-2xl border border-border bg-card p-6 sm:p-8 shadow-sm">
              <div className="flex items-center gap-2 mb-6">
                <HelpCircle className="h-5 w-5 text-muted-foreground" />
                <h3 className="text-lg font-semibold text-foreground">Need more?</h3>
              </div>

              <div className="grid sm:grid-cols-3 gap-6">
                {addOns.map((addon, i) => {
                  const AddonIcon = addon.icon
                  const isMeson = addon.name.includes("Meson")
                  const isResearch = addon.name.includes("Research")
                  return (
                    <div key={i} className="flex items-start gap-4">
                      <div
                        className={`h-10 w-10 rounded-xl flex items-center justify-center shrink-0 ${
                          isMeson ? "bg-violet-100" : isResearch ? "bg-sky-100" : "bg-muted"
                        }`}
                      >
                        <AddonIcon
                          className={`h-5 w-5 ${isMeson ? "text-violet-600" : isResearch ? "text-sky-600" : "text-muted-foreground"}`}
                        />
                      </div>
                      <div>
                        <div className="flex items-center gap-3 flex-wrap">
                          <p className="font-medium text-foreground">{addon.name}</p>
                          <span
                            className={`text-sm font-medium ${isMeson ? "text-violet-600" : isResearch ? "text-sky-600" : "text-primary"}`}
                          >
                            {addon.price}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">{addon.description}</p>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            <div className="mt-8 rounded-3xl border border-border bg-gradient-to-br from-muted/50 to-white p-8 text-center shadow-sm">
              <h3 className="text-xl font-semibold text-foreground">Need enterprise scale?</h3>
              <p className="mt-2 text-muted-foreground">
                Custom agent counts, SLAs, dedicated infrastructure, and white-glove onboarding.
              </p>
              <Link
                href="/contact"
                className="mt-6 inline-flex items-center gap-2 rounded-full border border-border bg-card px-8 py-3 text-sm font-semibold text-foreground transition-all hover:bg-muted/50 hover:border-border shadow-sm"
              >
                Talk to Sales
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </section>

        {/* Meson Section */}
        <section className="relative py-24 border-t border-border bg-muted/50">
          <div className="absolute inset-0 bg-gradient-to-b from-violet-50 via-transparent to-transparent" />
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-violet-100 rounded-full blur-3xl opacity-30" />

          <div className="relative mx-auto max-w-7xl px-6">
            <div className="mx-auto max-w-4xl">
              <div className="text-center mb-12">
                <div className="inline-flex items-center gap-2 mb-4 rounded-full border border-violet-200 bg-violet-50 px-4 py-1.5">
                  <Blocks className="h-4 w-4 text-violet-600" />
                  <span className="text-sm font-medium text-violet-700">System Builder</span>
                </div>
                <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground">
                  Build your system with Meson
                </h2>
                <p className="mt-4 text-lg text-muted-foreground">
                  Meson creates agents, training, and workflows from a single request.
                </p>
              </div>

              <div className="rounded-3xl border border-violet-200 bg-card p-8 shadow-sm">
                <div className="grid md:grid-cols-3 gap-6">
                  <div className="text-center">
                    <div className="mx-auto h-16 w-16 rounded-2xl bg-violet-100 border border-violet-200 flex items-center justify-center mb-4">
                      <FileText className="h-7 w-7 text-violet-600" />
                    </div>
                    <h3 className="font-semibold text-foreground mb-2">Describe what you need</h3>
                    <p className="text-sm text-muted-foreground">
                      {'"Create a marketing agent for SaaS onboarding campaigns"'}
                    </p>
                  </div>

                  <div className="hidden md:flex items-center justify-center">
                    <div className="flex items-center gap-2">
                      <div className="h-px w-12 bg-gradient-to-r from-violet-300 to-violet-500" />
                      <Sparkles className="h-5 w-5 text-violet-500 animate-pulse" />
                      <div className="h-px w-12 bg-gradient-to-r from-violet-500 to-violet-300" />
                    </div>
                  </div>

                  <div className="text-center">
                    <div className="mx-auto h-16 w-16 rounded-2xl bg-primary/15 border border-primary/20 flex items-center justify-center mb-4">
                      <Check className="h-7 w-7 text-primary" />
                    </div>
                    <h3 className="font-semibold text-foreground mb-2">Meson generates</h3>
                    <p className="text-sm text-muted-foreground">
                      Agent config, training structure, workflows, sample outputs
                    </p>
                  </div>
                </div>

                <div className="mt-8 pt-6 border-t border-border text-center">
                  <p className="text-sm text-muted-foreground mb-4">Meson builds the system. Gravitre executes it.</p>
                  <div className="inline-flex items-center gap-4 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1.5">
                      <Check className="h-3.5 w-3.5 text-primary" />
                      Available in Control
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Check className="h-3.5 w-3.5 text-primary" />
                      Available in Command
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Value Explanation */}
        <section className="relative py-24 border-t border-border bg-card">
          <div className="mx-auto max-w-7xl px-6">
            <div className="mx-auto max-w-3xl">
              <div className="text-center mb-12">
                <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground">
                  Not another AI tool. This is execution.
                </h2>
              </div>

              <div className="grid sm:grid-cols-2 gap-6">
                {[
                  {
                    title: "Complete work, not suggestions",
                    description:
                      "Gravitre doesn't generate ideas—it completes work. Full campaigns, sequences, and reports, delivered.",
                  },
                  {
                    title: "Hours replaced, not added",
                    description: "Each output replaces hours of manual effort. Work that took a day now takes minutes.",
                  },
                  {
                    title: "Direct delivery",
                    description: "Outputs delivered directly to your tools—email, CRM, Slack. No copy-paste required.",
                  },
                  {
                    title: "Learns your business",
                    description:
                      "Agents are trained on your brand voice, ICP, and messaging. They get better with every use.",
                  },
                ].map((item, i) => (
                  <div
                    key={i}
                    className="rounded-2xl border border-border bg-muted/50 p-6 hover:border-border transition-colors"
                  >
                    <h3 className="font-semibold text-foreground mb-2">{item.title}</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">{item.description}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* How It Works */}
        <section className="relative py-24 border-t border-border bg-muted/50">
          <div className="mx-auto max-w-7xl px-6">
            <div className="text-center mb-16">
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground">How it works</h2>
              <p className="mt-4 text-muted-foreground">From request to delivery in four steps</p>
            </div>

            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {howItWorks.map((item, i) => (
                <div key={i} className="relative">
                  {i < howItWorks.length - 1 && (
                    <div className="hidden lg:block absolute top-8 left-full w-full h-px bg-gradient-to-r from-border to-transparent -translate-x-6" />
                  )}
                  <div className="rounded-2xl border border-border bg-card p-6 h-full shadow-sm">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted">
                        <item.icon className="h-5 w-5 text-muted-foreground" />
                      </div>
                      <span className="text-xs font-mono text-muted-foreground">{item.step}</span>
                    </div>
                    <h3 className="font-semibold text-foreground mb-2">{item.title}</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">{item.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {SHOW_MARKETING_TESTIMONIALS ? (
          <section className="relative py-24 border-t border-border bg-card">
            <div className="mx-auto max-w-7xl px-6">
              <div className="text-center mb-16">
                <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground">
                  Trusted by growing teams
                </h2>
                <p className="mt-4 text-muted-foreground">See what teams are saying about Gravitre</p>
              </div>

              <div className="grid md:grid-cols-3 gap-6">
                {[
                  {
                    quote:
                      "Gravitre cut our campaign production time by 80%. What used to take our team 2 days now takes 20 minutes.",
                    author: "Sarah Chen",
                    role: "Marketing Director",
                    company: "TechStart",
                    rating: 5,
                  },
                  {
                    quote:
                      "The agents actually understand our brand voice. The outputs feel like they were written by someone who has been here for years.",
                    author: "Marcus Johnson",
                    role: "Head of Operations",
                    company: "DataFlow",
                    rating: 5,
                  },
                  {
                    quote:
                      "Meson is a game-changer. I described what I needed and had a fully configured agent in minutes, not hours.",
                    author: "Emily Rodriguez",
                    role: "Growth Lead",
                    company: "CloudScale",
                    rating: 5,
                  },
                ].map((testimonial, i) => (
                  <div
                    key={i}
                    className="relative rounded-2xl border border-border bg-card p-6 shadow-sm hover:shadow-md transition-shadow"
                  >
                    <div className="flex gap-1 mb-4">
                      {Array.from({ length: testimonial.rating }).map((_, j) => (
                        <Star key={j} className="h-4 w-4 fill-amber-400 text-amber-400" />
                      ))}
                    </div>
                    <p className="text-foreground leading-relaxed mb-6">{`"${testimonial.quote}"`}</p>
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 rounded-full bg-gradient-to-br from-muted to-border flex items-center justify-center">
                        <span className="text-sm font-semibold text-muted-foreground">
                          {testimonial.author
                            .split(" ")
                            .map((n) => n[0])
                            .join("")}
                        </span>
                      </div>
                      <div>
                        <p className="font-medium text-foreground text-sm">{testimonial.author}</p>
                        <p className="text-xs text-muted-foreground">
                          {testimonial.role}, {testimonial.company}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-16 pt-12 border-t border-border text-center">
                <p className="text-sm text-muted-foreground mb-8">Used by marketing and ops teams at</p>
                <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-6">
                  {["Acme Corp", "TechStart", "DataFlow", "CloudScale", "MarketEdge"].map((company) => (
                    <span
                      key={company}
                      className="text-lg font-semibold text-muted-foreground hover:text-muted-foreground transition-colors"
                    >
                      {company}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </section>
        ) : null}

        {/* Comparison Table */}
        <section className="relative py-24 border-t border-border bg-muted/50 overflow-hidden">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-gradient-to-b from-amber-100/30 to-transparent rounded-full blur-3xl pointer-events-none" />

          <div className="relative mx-auto max-w-6xl px-6">
            <div className="text-center mb-16">
              <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-1.5 text-sm font-medium text-muted-foreground mb-4">
                <Sparkles className="h-4 w-4 text-amber-500" />
                Detailed comparison
              </span>
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground">Compare all features</h2>
              <p className="mt-4 text-muted-foreground max-w-xl mx-auto">{MARKETING_COPY.pricing.comparisonIntro}</p>
            </div>

            <div className="rounded-3xl border border-border bg-card overflow-hidden shadow-xl shadow-border/40">
              <div className="grid grid-cols-4 border-b border-border">
                <div className="p-6 bg-muted/50">
                  <span className="text-sm font-medium text-muted-foreground">Features by plan</span>
                </div>
                <PricingComparisonPrices />
              </div>

              <div className="divide-y divide-border">
                <div>
                  <div className="grid grid-cols-4 bg-muted/50/80">
                    <div className="px-6 py-3">
                      <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Usage & Limits</span>
                    </div>
                    <div className="px-6 py-3" />
                    <div className="px-6 py-3 bg-amber-50/50" />
                    <div className="px-6 py-3" />
                  </div>
                  {[
                    {
                      feature: "Monthly outputs",
                      node: "10",
                      control: "40",
                      command: "120",
                      tooltip: "Complete deliverables per month",
                    },
                    ...(SHOW_RESEARCH_LOOKUPS_PRICING
                      ? [
                          {
                            feature: "Research lookups",
                            node: "10",
                            control: "60",
                            command: "200",
                            tooltip: "Live internet research lookups per month",
                          },
                        ]
                      : []),
                    { feature: "AI Agents", node: "1", control: "2-3", command: "5-8", tooltip: "Concurrent AI workers" },
                    { feature: "Core Users", node: "1", control: "2", command: "5", tooltip: "Full access team members" },
                    { feature: "Lite Users", node: "2", control: "5", command: "Unlimited", tooltip: "View-only access" },
                  ].map((row, i) => (
                    <div key={i} className="grid grid-cols-4 group hover:bg-muted/50/50 transition-colors">
                      <div className="px-6 py-4 flex items-center gap-2">
                        <span className="text-sm text-foreground">{row.feature}</span>
                        <div className="relative group/tooltip">
                          <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                          <div className="absolute left-full ml-2 top-1/2 -translate-y-1/2 px-2 py-1 bg-foreground text-primary-foreground text-xs rounded opacity-0 group-hover/tooltip:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-10">
                            {row.tooltip}
                          </div>
                        </div>
                      </div>
                      <div className="px-6 py-4 text-center">
                        <span className="inline-flex items-center justify-center min-w-[3rem] px-2 py-1 rounded-full bg-muted text-sm font-semibold text-foreground">
                          {row.node}
                        </span>
                      </div>
                      <div className="px-6 py-4 text-center bg-amber-50/30">
                        <span className="inline-flex items-center justify-center min-w-[3rem] px-2 py-1 rounded-full bg-amber-100 text-sm font-semibold text-amber-700">
                          {row.control}
                        </span>
                      </div>
                      <div className="px-6 py-4 text-center">
                        <span className="inline-flex items-center justify-center min-w-[3rem] px-2 py-1 rounded-full bg-primary/15 text-sm font-semibold text-primary">
                          {row.command}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>

                <div>
                  <div className="grid grid-cols-4 bg-muted/50/80">
                    <div className="px-6 py-3">
                      <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">AI Capabilities</span>
                    </div>
                    <div className="px-6 py-3" />
                    <div className="px-6 py-3 bg-amber-50/50" />
                    <div className="px-6 py-3" />
                  </div>
                  {aiCapabilityRows.map((row, i) => (
                    <div key={i} className="grid grid-cols-4 group hover:bg-muted/50/50 transition-colors">
                      <div className="px-6 py-4">
                        <span className="text-sm text-foreground">{row.feature}</span>
                      </div>
                      <div className="px-6 py-4 flex justify-center">{renderPlanComparisonCell(row.node, "node")}</div>
                      <div className="px-6 py-4 flex justify-center bg-amber-50/30">
                        {renderPlanComparisonCell(row.control, "control")}
                      </div>
                      <div className="px-6 py-4 flex justify-center">{renderPlanComparisonCell(row.command, "command")}</div>
                    </div>
                  ))}
                </div>

                <div>
                  <div className="grid grid-cols-4 bg-muted/50/80">
                    <div className="px-6 py-3">
                      <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        Integrations & Delivery
                      </span>
                    </div>
                    <div className="px-6 py-3" />
                    <div className="px-6 py-3 bg-amber-50/50" />
                    <div className="px-6 py-3" />
                  </div>
                  {[
                    { feature: "Email delivery", node: true, control: true, command: true },
                    { feature: "Slack delivery", node: false, control: true, command: true },
                    { feature: "CRM + Outlook integrations", node: false, control: true, command: true },
                    { feature: "Advanced integrations", node: false, control: false, command: true },
                  ].map((row, i) => (
                    <div key={i} className="grid grid-cols-4 group hover:bg-muted/50/50 transition-colors">
                      <div className="px-6 py-4">
                        <span className="text-sm text-foreground">{row.feature}</span>
                      </div>
                      <div className="px-6 py-4 flex justify-center">{renderPlanComparisonCell(row.node, "node")}</div>
                      <div className="px-6 py-4 flex justify-center bg-amber-50/30">
                        {renderPlanComparisonCell(row.control, "control")}
                      </div>
                      <div className="px-6 py-4 flex justify-center">{renderPlanComparisonCell(row.command, "command")}</div>
                    </div>
                  ))}
                </div>

                <div>
                  <div className="grid grid-cols-4 bg-muted/50/80">
                    <div className="px-6 py-3">
                      <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        Support & Collaboration
                      </span>
                    </div>
                    <div className="px-6 py-3" />
                    <div className="px-6 py-3 bg-amber-50/50" />
                    <div className="px-6 py-3" />
                  </div>
                  {[
                    { feature: "Community support", node: true, control: true, command: true },
                    { feature: "Priority support", node: false, control: true, command: true },
                    { feature: "Dedicated support", node: false, control: false, command: true },
                    { feature: "Team collaboration workspace", node: false, control: false, command: true },
                    { feature: "Approvals + workflows", node: false, control: false, command: true },
                  ].map((row, i) => (
                    <div key={i} className="grid grid-cols-4 group hover:bg-muted/50/50 transition-colors">
                      <div className="px-6 py-4">
                        <span className="text-sm text-foreground">{row.feature}</span>
                      </div>
                      <div className="px-6 py-4 flex justify-center">{renderPlanComparisonCell(row.node, "node")}</div>
                      <div className="px-6 py-4 flex justify-center bg-amber-50/30">
                        {renderPlanComparisonCell(row.control, "control")}
                      </div>
                      <div className="px-6 py-4 flex justify-center">{renderPlanComparisonCell(row.command, "command")}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-4 border-t border-border bg-muted/50/50">
                <div className="p-6" />
                {[
                  { name: "Node", highlighted: false },
                  { name: "Control", highlighted: true },
                  { name: "Command", highlighted: false },
                ].map((plan) => (
                  <div key={plan.name} className={`p-6 text-center ${plan.highlighted ? "bg-amber-50/50" : ""}`}>
                    <Link
                      href="/get-started"
                      className={`inline-flex items-center justify-center gap-2 rounded-full px-6 py-2.5 text-sm font-semibold transition-all ${
                        plan.highlighted
                          ? "bg-foreground text-primary-foreground hover:bg-foreground/90 shadow-lg shadow-foreground/20"
                          : "border border-border bg-card text-foreground hover:bg-muted/50 hover:border-border"
                      }`}
                    >
                      Get started
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Trust Badges */}
        <section className="relative py-16 border-t border-border bg-card">
          <div className="mx-auto max-w-5xl px-6">
            <div className="grid sm:grid-cols-4 gap-6">
              {[
                { icon: Shield, title: "Enterprise-grade security", description: "End-to-end encryption" },
                { icon: Clock, title: "7-day free trial", description: "Full access to all features" },
                { icon: RefreshCcw, title: "Cancel anytime", description: "No long-term contracts" },
                { icon: BadgeCheck, title: "Money-back guarantee", description: "30-day refund policy" },
              ].map((badge, i) => (
                <div key={i} className="text-center">
                  <div className="mx-auto h-12 w-12 rounded-xl bg-muted flex items-center justify-center mb-3">
                    <badge.icon className="h-6 w-6 text-muted-foreground" />
                  </div>
                  <p className="font-medium text-foreground text-sm">{badge.title}</p>
                  <p className="text-xs text-muted-foreground mt-1">{badge.description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="relative py-24 border-t border-border bg-muted/50">
          <div className="mx-auto max-w-3xl px-6">
            <div className="text-center mb-16">
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground">
                Frequently asked questions
              </h2>
            </div>

            <PricingFaqAccordion />
          </div>
        </section>

        {/* Final CTA */}
        <section className="relative py-24 border-t border-border bg-card">
          <div className="absolute inset-0 bg-gradient-to-t from-amber-50 via-transparent to-transparent" />
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-amber-100 rounded-full blur-3xl opacity-40" />

          <div className="relative mx-auto max-w-7xl px-6">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground">
                {MARKETING_COPY.pricing.cta.title}
              </h2>
              <p className="mt-4 text-muted-foreground">{MARKETING_COPY.pricing.cta.subtitle}</p>
              <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link
                  href="/get-started"
                  className="group inline-flex items-center gap-2 rounded-full bg-foreground px-8 py-4 text-base font-semibold text-primary-foreground transition-all hover:bg-foreground/90 shadow-lg shadow-foreground/20"
                >
                  Start your 7-day free trial
                  <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-1" />
                </Link>
                <Link
                  href="/get-started"
                  className="group inline-flex items-center gap-2 rounded-full border border-border bg-card px-6 py-4 text-sm font-semibold text-foreground transition-all hover:bg-muted/50 hover:border-border"
                >
                  Start free — no card required
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                </Link>
              </div>
              <p className="mt-4 text-sm text-muted-foreground">Full access for 7 days. Cancel anytime.</p>
            </div>
          </div>
        </section>
      </div>
    </PricingAnnualProvider>
  )
}
