import Link from "next/link"
import dynamic from "next/dynamic"
import { ArrowRight } from "lucide-react"
import { IntegrationsGrid } from "@/components/gravitre/platform-logos"
import { IntegrationStrip } from "@/components/marketing/integration-strip"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { HeroParallax } from "@/components/marketing/home/hero-parallax"
import { HomeNarrativeSections } from "@/components/marketing/home/home-narrative-sections"
import { IntelligenceField } from "@/components/gravitre/visual"
import { ProductFrame } from "@/components/marketing/product-frame"

const ProductShowcase = dynamic(
  () => import("@/components/marketing/product-showcase").then((m) => m.ProductShowcase),
  { ssr: true },
)
const DesktopDownloadSection = dynamic(
  () =>
    import("@/components/marketing/desktop-download-section").then((m) => m.DesktopDownloadSection),
  { ssr: true },
)

/**
 * Home — UI 3.0 Phase 3: Hybrid A+B light-first marketing.
 * Product stage hero · mineral canvas · real product captures.
 */
export default function HomePage() {
  const n = MARKETING_COPY.homeNarrative

  return (
    <div className="relative overflow-hidden bg-[color:var(--g-canvas)]">
      <HeroParallax />

      <IntegrationStrip />

      <HomeNarrativeSections />

      <DesktopDownloadSection />

      <section
        className="relative border-t border-border bg-[color:var(--g-background)] py-28 sm:py-32"
        data-field-atmosphere="systems"
      >
        <div className="relative mx-auto max-w-7xl px-6">
          <div className="mx-auto mb-16 max-w-2xl text-center">
            <h2 className="text-4xl font-bold tracking-tight text-[color:var(--g-text-primary)]">
              Connects to your entire stack
            </h2>
            <p className="mt-4 text-[color:var(--g-text-secondary)]">
              50+ pre-built integrations when configured — with live health and executability checks.
            </p>
          </div>
          <IntegrationsGrid theme="light" />
        </div>
      </section>

      <section
        className="relative overflow-hidden border-t border-border bg-[color:var(--g-surface-2)]/60 py-28 sm:py-36"
        data-field-atmosphere="intelligence"
      >
        <IntelligenceField variant="section" atmosphere="intelligence" className="opacity-20" />
        <div className="relative mx-auto max-w-7xl px-6">
          <div className="mx-auto mb-16 max-w-2xl text-center">
            <span className="text-sm font-bold uppercase tracking-wide text-[color:var(--g-intelligence)]">
              Product truth
            </span>
            <h2 className="mt-4 text-4xl font-bold tracking-tight text-[color:var(--g-text-primary)] sm:text-5xl">
              The operating surfaces teams actually use
            </h2>
            <p className="mt-4 text-lg text-[color:var(--g-text-secondary)]">
              Real Gravitre UI captures — framed for clarity, not invented dashboards.
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
        className="relative overflow-hidden border-t border-border bg-[color:var(--g-canvas)] py-28 sm:py-36"
        data-field-atmosphere="agents"
      >
        <div className="relative mx-auto max-w-7xl px-6">
          <div className="mx-auto mb-16 max-w-2xl text-center">
            <h2 className="text-4xl font-bold tracking-tight text-[color:var(--g-text-primary)] sm:text-5xl">
              See the platform in motion
            </h2>
            <p className="mt-4 text-lg text-[color:var(--g-text-secondary)]">
              Agents, workflows, runs, and learning surfaces — proof after the promise.
            </p>
          </div>
          <ProductShowcase />
        </div>
      </section>

      <section
        className="relative border-t border-border bg-[color:var(--g-surface-2)]/50 py-28 sm:py-36"
        data-field-atmosphere="balanced"
      >
        <div className="relative mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-3xl text-center">
            <h2 className="text-4xl font-bold tracking-[-0.03em] text-[color:var(--g-text-primary)] sm:text-5xl lg:text-6xl">
              {MARKETING_COPY.cta.title}
            </h2>
            <p className="mt-6 text-lg text-[color:var(--g-text-secondary)]">{MARKETING_COPY.cta.subtitle}</p>
            <p className="mt-4 text-base font-medium text-[color:var(--g-text-primary)]">{n.differentiation}</p>
            <div className="mt-12 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href="/get-started"
                className="group relative inline-flex items-center gap-2 overflow-hidden rounded-full bg-primary px-8 py-4 text-base font-semibold text-primary-foreground shadow-[var(--g-shadow-elevated)] transition-all duration-[var(--g-duration-micro)] hover:opacity-95 active:scale-[0.98]"
              >
                <span className="absolute inset-0 bg-gradient-to-b from-white/20 to-transparent opacity-50" />
                <span className="relative">{MARKETING_COPY.hero.ctaPrimary}</span>
                <ArrowRight
                  strokeWidth={2}
                  className="relative h-5 w-5 transition-transform group-hover:translate-x-1"
                />
              </Link>
              <Link
                href="/contact"
                className="inline-flex items-center gap-2 rounded-full border border-border bg-[color:var(--g-surface-1)] px-8 py-4 text-base font-semibold text-foreground shadow-[var(--g-shadow-surface)] transition-all hover:border-primary/40"
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
