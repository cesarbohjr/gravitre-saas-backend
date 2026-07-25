import Link from "next/link"
import { ArrowRight, Play } from "lucide-react"
import { IntegrationsGrid } from "@/components/gravitre/platform-logos"
import { ProductShowcase, HowItWorks, TestimonialsCarousel } from "@/components/marketing/product-showcase"
import { IntegrationStrip } from "@/components/marketing/integration-strip"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { SHOW_MARKETING_TESTIMONIALS } from "@/lib/marketing-flags"
import { AnimatedStat } from "@/components/marketing/home/animated-stat"
import { FeatureCard } from "@/components/marketing/home/feature-card"
import { FloatingOrb } from "@/components/marketing/home/floating-orb"
import { HeroParallax } from "@/components/marketing/home/hero-parallax"
import {
  AgentsStepVisual,
  ConnectorsStepVisual,
  GibeHonestyStepVisual,
} from "@/components/marketing/home/how-it-works-step-visuals"

/**
 * Home stays a short pitch + proof + CTA.
 * Deep Features / Technology / Marketplace content lives only on those nav pages
 * (see FeaturesLegacyContent exclude on /features) — do not re-embed it here.
 */
export default function HomePage() {
  return (
    <div className="relative overflow-hidden bg-white">
      <HeroParallax />

      <IntegrationStrip />

      <section className="relative py-32 bg-white">
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

      <section className="relative py-32 bg-zinc-50">
        <FloatingOrb className="w-[500px] h-[500px] bg-emerald-100 top-1/4 -left-64" delay={1} />

        <div className="relative mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-2xl text-center mb-20">
            <h2 className="text-4xl sm:text-5xl font-bold tracking-tight text-zinc-900">
              Built for operators, not chatbots
            </h2>
            <p className="mt-4 text-lg text-zinc-600">
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
              className="inline-flex items-center gap-1.5 rounded-full border border-zinc-300 bg-white px-4 py-2 font-medium text-zinc-800 transition-colors hover:bg-zinc-50"
            >
              Platform features
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
            <Link
              href="/features/technology"
              className="inline-flex items-center gap-1.5 rounded-full border border-zinc-300 bg-white px-4 py-2 font-medium text-zinc-800 transition-colors hover:bg-zinc-50"
            >
              Technology
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
            <Link
              href="/features/marketplace"
              className="inline-flex items-center gap-1.5 rounded-full border border-zinc-300 bg-white px-4 py-2 font-medium text-zinc-800 transition-colors hover:bg-zinc-50"
            >
              Marketplace
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </section>

      <section className="relative py-32 border-t border-zinc-200 bg-white">
        <div className="mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-2xl text-center mb-16">
            <h2 className="text-4xl font-bold tracking-tight text-zinc-900">Connects to your entire stack</h2>
            <p className="mt-4 text-zinc-600">
              50+ pre-built integrations when configured — with live health and executability checks.
            </p>
          </div>

          <IntegrationsGrid theme="light" />
        </div>
      </section>

      <section className="relative py-32 border-t border-zinc-200 overflow-hidden bg-zinc-50">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-emerald-50/30 to-transparent" />

        <div className="relative mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-2xl text-center mb-16">
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 mb-6">
              <Play strokeWidth={1.5} className="h-4 w-4 text-emerald-600" />
              <span className="text-sm font-medium text-emerald-700">Discover the platform</span>
            </div>
            <h2 className="text-4xl sm:text-5xl font-bold tracking-tight text-zinc-900">
              Powerful features, simple interface
            </h2>
            <p className="mt-4 text-lg text-zinc-600">
              See agents, workflows, runs, and learning surfaces in one interface.
            </p>
          </div>

          <ProductShowcase />
        </div>
      </section>

      <section className="relative py-32 border-t border-zinc-200 bg-white">
        <div className="mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-2xl text-center mb-20">
            <span className="text-sm font-semibold text-emerald-600 tracking-wide uppercase">
              {MARKETING_COPY.howItWorks.eyebrow}
            </span>
            <h2 className="mt-4 text-4xl sm:text-5xl font-bold tracking-tight text-zinc-900">
              {MARKETING_COPY.howItWorks.title}
            </h2>
            <p className="mt-4 text-lg text-zinc-600">{MARKETING_COPY.howItWorks.subtitle}</p>
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
        <section className="relative py-32 border-t border-zinc-200 bg-zinc-50">
          <div className="mx-auto max-w-7xl px-6">
            <div className="mx-auto max-w-2xl text-center mb-16">
              <span className="text-sm font-semibold text-emerald-600 tracking-wide uppercase">Testimonials</span>
              <h2 className="mt-4 text-4xl font-bold tracking-tight text-zinc-900">What people say</h2>
              <p className="mt-4 text-zinc-600">
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

      <section className="relative py-32 bg-zinc-50">
        <div className="absolute inset-0 bg-gradient-to-t from-emerald-50 via-transparent to-transparent" />
        <FloatingOrb className="w-[600px] h-[600px] bg-emerald-100 -bottom-48 left-1/2 -translate-x-1/2" />

        <div className="relative mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-3xl text-center">
            <h2 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-zinc-900">
              {MARKETING_COPY.cta.title}
            </h2>
            <p className="mt-6 text-lg text-zinc-600">{MARKETING_COPY.cta.subtitle}</p>
            <div className="mt-12 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/get-started"
                className="group relative inline-flex items-center gap-2 rounded-full bg-zinc-900 px-8 py-4 text-base font-semibold text-white transition-all hover:bg-zinc-800"
              >
                <span>Start Free Trial</span>
                <ArrowRight strokeWidth={1.5} className="h-5 w-5 transition-transform group-hover:translate-x-1" />
              </Link>
              <Link
                href="/contact"
                className="inline-flex items-center gap-2 rounded-full border border-zinc-300 bg-white px-8 py-4 text-base font-semibold text-zinc-900 shadow-sm transition-all hover:bg-zinc-50"
              >
                Contact Sales
              </Link>
            </div>
            <p className="mt-6 text-sm text-zinc-500">Start your 7-day free trial today.</p>
          </div>
        </div>
      </section>
    </div>
  )
}
