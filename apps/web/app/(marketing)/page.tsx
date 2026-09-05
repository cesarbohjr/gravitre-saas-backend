import Link from "next/link"
import dynamic from "next/dynamic"
import { ArrowRight, Play } from "lucide-react"
import { IntegrationsGrid } from "@/components/gravitre/platform-logos"
import { IntegrationStrip } from "@/components/marketing/integration-strip"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { SHOW_MARKETING_TESTIMONIALS } from "@/lib/marketing-flags"
import { HeroParallax } from "@/components/marketing/home/hero-parallax"
import {
  AgentsStepVisual,
  ConnectorsStepVisual,
  GibeHonestyStepVisual,
} from "@/components/marketing/home/how-it-works-step-visuals"
import { MarketingBackgroundLines } from "@/components/marketing/home/marketing-background-lines-client"
import { IntelligenceField } from "@/components/gravitre/visual"
import { ProductFrame } from "@/components/marketing/product-frame"

const AnimatedStat = dynamic(
  () => import("@/components/marketing/home/animated-stat").then((m) => m.AnimatedStat),
  { ssr: true },
)
const FeatureCard = dynamic(
  () => import("@/components/marketing/home/feature-card").then((m) => m.FeatureCard),
  { ssr: true },
)
const FloatingOrb = dynamic(
  () => import("@/components/marketing/home/floating-orb").then((m) => m.FloatingOrb),
  { ssr: true },
)
const ProductShowcase = dynamic(
  () => import("@/components/marketing/product-showcase").then((m) => m.ProductShowcase),
  { ssr: true },
)
const HowItWorks = dynamic(
  () => import("@/components/marketing/product-showcase").then((m) => m.HowItWorks),
  { ssr: true },
)
const TestimonialsCarousel = dynamic(
  () => import("@/components/marketing/product-showcase").then((m) => m.TestimonialsCarousel),
  { ssr: true },
)
const DesktopDownloadSection = dynamic(
  () =>
    import("@/components/marketing/desktop-download-section").then((m) => m.DesktopDownloadSection),
  { ssr: true },
)

/**
 * Home stays a short pitch + proof + CTA.
 * Design Pass 2 Agenforce-caliber: atmosphere narrative + real product frames.
 */
export default function HomePage() {
  return (
    <div className="relative overflow-hidden bg-background">
      <HeroParallax />

      <IntegrationStrip />

      <section className="relative py-28 sm:py-32 bg-background">
        <div className="mx-auto max-w-7xl px-6">
          <div className="grid gap-12 sm:grid-cols-2 lg:grid-cols-4">
            {MARKETING_COPY.stats.map((stat) => (
              <AnimatedStat
                key={stat.label}
                value={stat.value}
                label={stat.label}
                suffix={"suffix" in stat ? stat.suffix : ""}
              />
            ))}
          </div>
        </div>
      </section>

      <section
        className="relative py-28 sm:py-36 bg-muted/40"
        data-field-atmosphere="agents"
      >
        <IntelligenceField variant="section" atmosphere="agents" className="opacity-75" />
        <MarketingBackgroundLines className="opacity-50" />
        <FloatingOrb className="w-[500px] h-[500px] bg-[color:var(--g-intelligence)]/12 top-1/4 -left-64" delay={1} />
        <FloatingOrb className="w-[420px] h-[420px] bg-primary/10 bottom-1/4 -right-48" delay={2.2} />

        <div className="relative mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-2xl text-center mb-20">
            <h2 className="text-4xl sm:text-5xl font-bold tracking-tight text-foreground">
              Built for operators, not chatbots
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Connect, learn, execute, and measure — with approval gates and evidence at every step.
            </p>
          </div>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {MARKETING_COPY.homeFeatures.map((feature, i) => (
              <FeatureCard
                key={feature.title}
                iconIndex={i}
                title={feature.title}
                description={feature.description}
                index={i}
              />
            ))}
          </div>

          <div className="mt-12 flex flex-wrap items-center justify-center gap-3 text-sm">
            {[
              { href: "/features", label: "Platform features" },
              { href: "/features/technology", label: "Technology" },
              { href: "/features/marketplace", label: "Marketplace" },
              { href: "/features/extension", label: "Browser extension" },
              { href: "/download", label: "Desktop download" },
            ].map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)]/80 px-4 py-2 font-medium text-foreground shadow-[var(--g-shadow-surface)] backdrop-blur-sm transition-all duration-[var(--g-duration-micro)] hover:border-[color:var(--g-border-active)] hover:bg-[color:var(--g-surface-2)]"
              >
                {item.label}
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            ))}
          </div>
        </div>
      </section>

      <DesktopDownloadSection />

      <section
        className="relative py-28 sm:py-32 border-t border-border bg-background"
        data-field-atmosphere="systems"
      >
        <IntelligenceField variant="section" atmosphere="systems" className="opacity-40" />
        <div className="relative mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-2xl text-center mb-16">
            <h2 className="text-4xl font-bold tracking-tight text-foreground">
              Connects to your entire stack
            </h2>
            <p className="mt-4 text-muted-foreground">
              50+ pre-built integrations when configured — with live health and executability checks.
            </p>
          </div>
          <IntegrationsGrid theme="dark" />
        </div>
      </section>

      {/* Real product surfaces — art-directed frames */}
      <section
        className="relative overflow-hidden border-t border-border bg-muted/30 py-28 sm:py-36"
        data-field-atmosphere="intelligence"
      >
        <IntelligenceField variant="section" atmosphere="intelligence" className="opacity-55" />
        <div className="relative mx-auto max-w-7xl px-6">
          <div className="mx-auto mb-16 max-w-2xl text-center">
            <span className="text-sm font-semibold uppercase tracking-wide text-[color:var(--g-intelligence-bright)]">
              Product truth
            </span>
            <h2 className="mt-4 text-4xl sm:text-5xl font-bold tracking-tight text-foreground">
              The operating surfaces teams actually use
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Real Gravitre UI captures — chat, agents, approvals, connectors — framed for clarity,
              not invented dashboards.
            </p>
          </div>

          <div className="grid gap-10 lg:grid-cols-2 lg:gap-12">
            <ProductFrame
              src="/product/app-ai.png"
              alt="Gravitre AI chat with connector-aware routing"
              chromeLabel="gravitre.app/ai"
              treatment="perspective"
              glowTone="intelligence"
              caption="Fixture demo surface — not live customer metrics"
            />
            <ProductFrame
              src="/product/app-approvals.png"
              alt="Gravitre approval gate with human review"
              chromeLabel="gravitre.app/approvals"
              treatment="fade-system"
              glowTone="operational"
              caption="Human gate before execution"
            />
          </div>

          <div className="mt-12 grid gap-8 md:grid-cols-3">
            <ProductFrame
              src="/product/app-agents.png"
              alt="Gravitre agents directory"
              chromeLabel="gravitre.app/agents"
              treatment="detail"
              glowTone="intelligence"
            />
            <ProductFrame
              src="/product/app-workflows.png"
              alt="Gravitre workflow builder"
              chromeLabel="gravitre.app/workflows"
              treatment="full"
              glowTone="none"
            />
            <ProductFrame
              src="/product/app-connectors.png"
              alt="Gravitre connectors health"
              chromeLabel="gravitre.app/connectors"
              treatment="stacked"
              glowTone="operational"
              secondarySrc="/product/app-activity.png"
              secondaryAlt="Activity runs"
            />
          </div>
        </div>
      </section>

      <section
        className="relative py-28 sm:py-36 border-t border-border overflow-hidden bg-muted/40"
        data-field-atmosphere="agents"
      >
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-primary/5 to-[color:var(--g-intelligence)]/5" />
        <IntelligenceField variant="section" atmosphere="agents" className="opacity-45" />

        <div className="relative mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-2xl text-center mb-16">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-2 mb-6">
              <Play strokeWidth={1.5} className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium text-primary">Discover the platform</span>
            </div>
            <h2 className="text-4xl sm:text-5xl font-bold tracking-tight text-foreground">
              Powerful features, simple interface
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              See agents, workflows, runs, and learning surfaces in one interface.
            </p>
          </div>

          <ProductShowcase />
        </div>
      </section>

      <section
        className="relative border-t border-border bg-background py-28 sm:py-36"
        data-field-atmosphere="approval"
      >
        <IntelligenceField variant="section" atmosphere="approval" className="opacity-45" />
        <MarketingBackgroundLines className="opacity-55" />
        <div className="relative mx-auto max-w-7xl px-6">
          <div className="mx-auto mb-20 max-w-2xl text-center">
            <span className="text-sm font-semibold uppercase tracking-wide text-primary">
              {MARKETING_COPY.howItWorks.eyebrow}
            </span>
            <h2 className="mt-4 text-4xl sm:text-5xl font-bold tracking-tight text-foreground">
              {MARKETING_COPY.howItWorks.title}
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">{MARKETING_COPY.howItWorks.subtitle}</p>
          </div>

          <HowItWorks
            steps={[
              {
                number: MARKETING_COPY.howItWorks.steps[0].number,
                title: MARKETING_COPY.howItWorks.steps[0].title,
                description: MARKETING_COPY.howItWorks.steps[0].description,
                visual: <ConnectorsStepVisual />,
              },
              {
                number: MARKETING_COPY.howItWorks.steps[1].number,
                title: MARKETING_COPY.howItWorks.steps[1].title,
                description: MARKETING_COPY.howItWorks.steps[1].description,
                visual: <GibeHonestyStepVisual />,
              },
              {
                number: MARKETING_COPY.howItWorks.steps[2].number,
                title: MARKETING_COPY.howItWorks.steps[2].title,
                description: MARKETING_COPY.howItWorks.steps[2].description,
                visual: <AgentsStepVisual />,
              },
            ]}
          />
        </div>
      </section>

      {SHOW_MARKETING_TESTIMONIALS ? (
        <section className="relative py-32 border-t border-border bg-muted/50">
          <div className="mx-auto max-w-7xl px-6">
            <div className="mx-auto max-w-2xl text-center mb-16">
              <span className="text-sm font-semibold text-primary tracking-wide uppercase">
                Testimonials
              </span>
              <h2 className="mt-4 text-4xl font-bold tracking-tight text-foreground">
                What people say
              </h2>
              <p className="mt-4 text-muted-foreground">
                With over 10,000 clients served, here&apos;s what they have to say
              </p>
            </div>

            <div className="max-w-3xl mx-auto">
              <TestimonialsCarousel
                testimonials={[
                  {
                    quote:
                      "Gravitre is a strong signal of how enterprise automation will evolve. It is an early adopter of the agentic approach, which will become increasingly effective and trusted.",
                    author: "Sarah Chen",
                    role: "VP of Operations",
                    company: "TechFlow Inc",
                  },
                  {
                    quote:
                      "The AI agents are intuitive, easy to configure, and have been effectively handling our workflows for nearly a year. The ROI has been incredible.",
                    author: "Michael Torres",
                    role: "CTO",
                    company: "DataSync",
                  },
                  {
                    quote:
                      "Gravitre gave us a powerful, flexible way to launch our AI automation without the complexity we saw in other platforms. The team support is exceptional.",
                    author: "Emily Watson",
                    role: "Director of Engineering",
                    company: "CloudBase",
                  },
                ]}
              />
            </div>
          </div>
        </section>
      ) : null}

      <section
        className="relative py-28 sm:py-36 bg-muted/40"
        data-field-atmosphere="balanced"
      >
        <IntelligenceField variant="section" atmosphere="balanced" className="opacity-70" />
        <div className="absolute inset-0 bg-gradient-to-t from-primary/8 via-transparent to-[color:var(--g-intelligence)]/6" />
        <FloatingOrb className="w-[600px] h-[600px] bg-primary/10 -bottom-48 left-1/2 -translate-x-1/2" />

        <div className="relative mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-3xl text-center">
            <h2 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-[-0.03em] text-foreground">
              {MARKETING_COPY.cta.title}
            </h2>
            <p className="mt-6 text-lg text-muted-foreground">{MARKETING_COPY.cta.subtitle}</p>
            <div className="mt-12 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/get-started"
                className="group relative inline-flex items-center gap-2 overflow-hidden rounded-full bg-primary px-8 py-4 text-base font-semibold text-primary-foreground shadow-[var(--g-shadow-elevated)] transition-all duration-[var(--g-duration-micro)] hover:opacity-95 hover:shadow-[var(--g-glow-operational)] active:scale-[0.98]"
              >
                <span className="absolute inset-0 bg-gradient-to-b from-white/15 to-transparent opacity-60" />
                <span className="relative">Start Free Trial</span>
                <ArrowRight
                  strokeWidth={1.5}
                  className="relative h-5 w-5 transition-transform group-hover:translate-x-1"
                />
              </Link>
              <Link
                href="/contact"
                className="inline-flex items-center gap-2 rounded-full border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)]/80 px-8 py-4 text-base font-semibold text-foreground shadow-[var(--g-shadow-surface)] backdrop-blur-sm transition-all hover:border-[color:var(--g-intelligence)]/30 hover:bg-[color:var(--g-surface-2)]"
              >
                Contact Sales
              </Link>
            </div>
            <p className="mt-6 text-sm text-muted-foreground">Start your 7-day free trial today.</p>
          </div>
        </div>
      </section>
    </div>
  )
}
