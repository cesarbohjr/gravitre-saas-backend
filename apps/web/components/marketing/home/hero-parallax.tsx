"use client"

import Link from "next/link"
import { motion, useScroll, useTransform } from "framer-motion"
import { useRef } from "react"
import { ArrowRight, Play } from "lucide-react"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { useMotionPrefs, timing } from "@/lib/animations"
import { IntelligenceField } from "@/components/gravitre/visual"
import { MarketingSpotlight } from "./marketing-spotlight"
import { ProductPreview } from "./product-preview"

/**
 * Marketing home first viewport — Agenforce-caliber craft, Gravitre product truth.
 * Budget: brand · headline · support · CTA · dominant product visual.
 */

const ease = [0.22, 1, 0.36, 1] as const

export function HeroParallax() {
  const heroRef = useRef(null)
  const { reduced } = useMotionPrefs()
  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ["start start", "end start"],
  })
  const heroOpacity = useTransform(scrollYProgress, [0, 0.55], [1, reduced ? 1 : 0])
  const heroScale = useTransform(scrollYProgress, [0, 0.55], [1, reduced ? 1 : 0.97])
  const heroY = useTransform(scrollYProgress, [0, 0.55], [0, reduced ? 0 : 72])

  return (
    <section
      ref={heroRef}
      className="relative flex min-h-[100svh] items-center justify-center bg-background text-foreground"
      data-marketing-hero=""
      data-field-atmosphere="intelligence"
    >
      <IntelligenceField variant="hero" atmosphere="intelligence" />
      <MarketingSpotlight tone="intelligence" interactive className="opacity-90" />

      <motion.div
        style={{ opacity: heroOpacity, scale: heroScale, y: heroY }}
        className="relative mx-auto max-w-7xl px-6 py-24 sm:py-28 lg:py-32"
      >
        <div className="mx-auto max-w-4xl text-center">
          <motion.p
            initial={reduced ? false : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, ease }}
            className="text-sm font-semibold uppercase tracking-[0.28em] text-[color:var(--g-intelligence-bright)]"
          >
            Gravitre
          </motion.p>

          <motion.h1
            initial={reduced ? false : { opacity: 0, y: 22 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: reduced ? 0 : 0.08, ease }}
            className="mt-6 text-[2.75rem] font-bold leading-[1.05] tracking-[-0.04em] sm:text-7xl lg:text-[5.25rem]"
          >
            <span className="block text-foreground">{MARKETING_COPY.hero.headline[0]}</span>
            <span className="mt-1 block bg-gradient-to-r from-[color:var(--g-emerald)] via-[color:var(--g-intelligence-bright)] to-[color:var(--g-intelligence)] bg-clip-text text-transparent">
              {MARKETING_COPY.hero.headline[1]}
            </span>
          </motion.h1>

          <motion.p
            initial={reduced ? false : { opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.65, delay: reduced ? 0 : 0.16, ease }}
            className="mx-auto mt-8 max-w-2xl text-lg leading-relaxed text-muted-foreground sm:text-xl sm:leading-relaxed"
          >
            {MARKETING_COPY.hero.subhead}
          </motion.p>

          <motion.div
            initial={reduced ? false : { opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: reduced ? 0 : 0.24, ease }}
            className="mt-12 flex flex-col items-center justify-center gap-4 sm:flex-row"
          >
            <Link
              href="/get-started"
              className="group relative inline-flex items-center gap-2 overflow-hidden rounded-full bg-primary px-8 py-4 text-base font-semibold text-primary-foreground shadow-[var(--g-shadow-elevated)] transition-all duration-[var(--g-duration-micro)] hover:opacity-95 hover:shadow-[var(--g-glow-operational)] active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              <span className="absolute inset-0 bg-gradient-to-b from-white/15 to-transparent opacity-60" />
              <span className="relative">{MARKETING_COPY.hero.ctaPrimary}</span>
              <ArrowRight
                strokeWidth={1.5}
                className="relative h-5 w-5 transition-transform duration-[var(--g-duration-micro)] group-hover:translate-x-1"
              />
            </Link>
            <Link
              href="/features"
              className="group inline-flex items-center gap-2 rounded-full border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)]/70 px-8 py-4 text-base font-semibold text-foreground shadow-[var(--g-shadow-surface)] backdrop-blur-md transition-all duration-[var(--g-duration-micro)] hover:border-[color:var(--g-intelligence)]/35 hover:bg-[color:var(--g-surface-2)] active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Play strokeWidth={1.5} className="h-5 w-5 fill-foreground" />
              <span>{MARKETING_COPY.hero.ctaSecondary}</span>
            </Link>
          </motion.div>
        </div>

        <motion.div
          initial={reduced ? false : { opacity: 0, y: 36 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.85, delay: reduced ? 0 : 0.32, ease }}
          className="mt-16 sm:mt-20 lg:mt-24"
        >
          <ProductPreview />
        </motion.div>
      </motion.div>

      {!reduced ? (
        <div className="absolute bottom-8 left-1/2 flex -translate-x-1/2 flex-col items-center gap-2 text-muted-foreground">
          <span className="text-[10px] uppercase tracking-[0.28em]">Scroll</span>
          <motion.div
            className="h-8 w-px bg-gradient-to-b from-[color:var(--g-intelligence)]/70 to-transparent"
            animate={{ opacity: [0.35, 1, 0.35] }}
            transition={{ duration: timing.slow * 2, repeat: Infinity, ease: "easeInOut" }}
          />
        </div>
      ) : null}
    </section>
  )
}
