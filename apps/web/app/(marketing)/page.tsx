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

// Below-fold client islands — keep HeroParallax eager for LCP; split the rest.
const AnimatedStat = dynamic(
  () => import("@/components/marketing/home/animated-stat").then((m) => m.AnimatedStat),
  { ssr: true }
)
const FeatureCard = dynamic(
  () => import("@/components/marketing/home/feature-card").then((m) => m.FeatureCard),
  { ssr: true }
)
const FloatingOrb = dynamic(
  () => import("@/components/marketing/home/floating-orb").then((m) => m.FloatingOrb),
  { ssr: true }
)
const ProductShowcase = dynamic(
  () => import("@/components/marketing/product-showcase").then((m) => m.ProductShowcase),
  { ssr: true }
)
const HowItWorks = dynamic(
  () => import("@/components/marketing/product-showcase").then((m) => m.HowItWorks),
  { ssr: true }
)
const TestimonialsCarousel = dynamic(
  () => import("@/components/marketing/product-showcase").then((m) => m.TestimonialsCarousel),
  { ssr: true }
)
const DesktopDownloadSection = dynamic(
  () =>
    import("@/components/marketing/desktop-download-section").then((m) => m.DesktopDownloadSection),
  { ssr: true }
)
const MarketingBackgroundLines = dynamic(
  () =>
    import("@/components/marketing/home/marketing-background-lines").then(
      (m) => m.MarketingBackgroundLines,
    ),
  { ssr: false },
)

/**
 * Home stays a short pitch + proof + CTA.
 * Deep Features / Technology / Marketplace content lives only on those nav pages
 * (see FeaturesLegacyContent exclude on /features) — do not re-embed it here.
 */
export default function HomePage() {
  return (
    <div className="relative overflow-hidden bg-background">
      <HeroParallax />

      <IntegrationStrip />

      <section className="relative py-32 bg-background">
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

      <section className="relative py-32 bg-muted/50">
        <MarketingBackgroundLines />
        <FloatingOrb className="w-[500px] h-[500px] bg-primary/10 top-1/4 -left-64" delay={1} />

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
            <Link
              href="/features"
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-4 py-2 font-medium text-foreground transition-colors hover:bg-muted/50"
            >
              Platform features
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
            <Link
              href="/features/technology"
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-4 py-2 font-medium text-foreground transition-colors hover:bg-muted/50"
            >
              Technology
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
            <Link
              href="/features/marketplace"
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-4 py-2 font-medium text-foreground transition-colors hover:bg-muted/50"
            >
              Marketplace
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
            <Link
              href="/features/extension"
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-4 py-2 font-medium text-foreground transition-colors hover:bg-muted/50"
            >
              Browser extension
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
            <Link
              href="/download"
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-4 py-2 font-medium text-foreground transition-colors hover:bg-muted/50"
            >
              Desktop download
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </section>

      <DesktopDownloadSection />

      <section className="relative py-32 border-t border-border bg-background">
        <div className="mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-2xl text-center mb-16">
            <h2 className="text-4xl font-bold tracking-tight text-foreground">Connects to your entire stack</h2>
            <p className="mt-4 text-muted-foreground">
              50+ pre-built integrations when configured — with live health and executability checks.
            </p>
          </div>

          <IntegrationsGrid theme="light" />
        </div>
      </section>

      <section className="relative py-32 border-t border-border overflow-hidden bg-muted/50">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-primary/5 to-transparent" />

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

      <section className="relative py-32 border-t border-border bg-background">
        <div className="mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-2xl text-center mb-20">
            <span className="text-sm font-semibold text-primary tracking-wide uppercase">
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
              <span className="text-sm font-semibold text-primary tracking-wide uppercase">Testimonials</span>
              <h2 className="mt-4 text-4xl font-bold tracking-tight text-foreground">What people say</h2>
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

      <section className="relative py-32 bg-muted/50">
        <div className="absolute inset-0 bg-gradient-to-t from-primary/5 via-transparent to-transparent" />
        <FloatingOrb className="w-[600px] h-[600px] bg-primary/10 -bottom-48 left-1/2 -translate-x-1/2" />

        <div className="relative mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-3xl text-center">
            <h2 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-foreground">
              {MARKETING_COPY.cta.title}
            </h2>
            <p className="mt-6 text-lg text-muted-foreground">{MARKETING_COPY.cta.subtitle}</p>
            <div className="mt-12 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/get-started"
                className="group relative inline-flex items-center gap-2 rounded-full bg-primary px-8 py-4 text-base font-semibold text-primary-foreground transition-all hover:opacity-90"
              >
                <span>Start Free Trial</span>
                <ArrowRight strokeWidth={1.5} className="h-5 w-5 transition-transform group-hover:translate-x-1" />
              </Link>
              <Link
                href="/contact"
                className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-8 py-4 text-base font-semibold text-foreground shadow-sm transition-all hover:bg-muted/50"
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
