import Link from "next/link"
import { IntegrationStrip } from "@/components/marketing/integration-strip"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { HeroParallax } from "@/components/marketing/home/hero-parallax"
import { HomeNarrativeSections } from "@/components/marketing/home/home-narrative-sections"
import { NucleoArrowRight } from "@/components/icons/nucleo/semantic"

/**
 * Home — UI 3.0: radical simplicity at the top, sophistication underneath.
 * Story only — Features / Technology / Marketplace / Extension / Download live in nav.
 */
export default function HomePage() {
  const n = MARKETING_COPY.homeNarrative

  return (
    <div className="relative overflow-hidden bg-[color:var(--g-canvas)]">
      <HeroParallax />

      <IntegrationStrip />

      <HomeNarrativeSections />

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
                <NucleoArrowRight
                  size={20}
                  strokeWidth={2}
                  className="relative transition-transform group-hover:translate-x-1"
                />
              </Link>
              <Link
                href="/contact"
                className="inline-flex items-center gap-2 rounded-full border border-border bg-[color:var(--g-surface-1)] px-8 py-4 text-base font-semibold text-foreground shadow-[var(--g-shadow-surface)] transition-all hover:border-primary/40"
              >
                Talk to us
              </Link>
            </div>
            <p className="mt-8 text-sm text-muted-foreground">
              Prefer detail?{" "}
              <Link href="/features" className="font-medium text-foreground underline-offset-4 hover:underline">
                Features
              </Link>
              {" · "}
              <Link href="/pricing" className="font-medium text-foreground underline-offset-4 hover:underline">
                Pricing
              </Link>
              {" · "}
              <Link href="/download" className="font-medium text-foreground underline-offset-4 hover:underline">
                Download
              </Link>
            </p>
            <p className="mt-4 text-sm text-muted-foreground">7-day free trial. No invented ROI required.</p>
          </div>
        </div>
      </section>
    </div>
  )
}
