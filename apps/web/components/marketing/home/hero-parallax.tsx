"use client"

import Link from "next/link"
import { motion, useScroll, useTransform } from "framer-motion"
import { useRef } from "react"
import { ArrowRight } from "lucide-react"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { TYPE_MARKETING } from "@/lib/design-system"
import { useMotionPrefs, timing } from "@/lib/animations"
import { MarketingSpotlight } from "./marketing-spotlight"
import { HybridHeroStage } from "./hybrid-hero-stage"
import { cn } from "@/lib/utils"

/**
 * UI 3.0 Phase 3 — Hybrid A+B hero.
 * Light mineral canvas · product stage as graphic · living execution beats.
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
  const heroScale = useTransform(scrollYProgress, [0, 0.55], [1, reduced ? 1 : 0.98])
  const heroY = useTransform(scrollYProgress, [0, 0.55], [0, reduced ? 0 : 48])

  return (
    <section
      ref={heroRef}
      className="relative flex min-h-[100svh] items-center justify-center overflow-hidden bg-[color:var(--g-canvas)] text-[color:var(--g-text-primary)]"
      data-marketing-hero=""
      data-ui30-hero="hybrid-ab"
    >
      {/* Soft directional light only — no grid / heavy field */}
      <MarketingSpotlight tone="neutral" interactive className="opacity-50" />
      <div
        className="pointer-events-none absolute inset-0"
        style={{ background: "var(--g-light-neutral)" }}
        aria-hidden
      />

      <motion.div
        style={{ opacity: heroOpacity, scale: heroScale, y: heroY }}
        className="relative mx-auto w-full max-w-7xl px-6 py-24 sm:py-28 lg:py-32"
      >
        <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:gap-14">
          <div className="max-w-xl lg:max-w-none">
            <motion.p
              initial={reduced ? false : { opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.55, ease }}
              className={cn(TYPE_MARKETING.label, "text-[color:var(--g-emerald-bright)]")}
            >
              {MARKETING_COPY.hero.badge}
            </motion.p>

            <motion.h1
              initial={reduced ? false : { opacity: 0, y: 22 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: reduced ? 0 : 0.08, ease }}
              className={cn(TYPE_MARKETING.display, "mt-5")}
            >
              <span className="block">
                {MARKETING_COPY.hero.headline[0]}{" "}
                <span className="block sm:inline">{MARKETING_COPY.hero.headline[1]}</span>
              </span>
            </motion.h1>

            <motion.p
              initial={reduced ? false : { opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.65, delay: reduced ? 0 : 0.16, ease }}
              className={cn(TYPE_MARKETING.lead, "mt-6 max-w-lg")}
            >
              {MARKETING_COPY.hero.subhead}
            </motion.p>

            <motion.div
              initial={reduced ? false : { opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: reduced ? 0 : 0.24, ease }}
              className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center"
            >
              <Link
                href="/get-started"
                className="group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-full bg-primary px-7 py-3.5 text-sm font-semibold text-primary-foreground shadow-[var(--g-shadow-elevated)] transition-all duration-[var(--g-duration-micro)] hover:opacity-95 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <span className="absolute inset-0 bg-gradient-to-b from-white/20 to-transparent opacity-50" />
                <span className="relative">{MARKETING_COPY.hero.ctaPrimary}</span>
                <ArrowRight
                  strokeWidth={2}
                  className="relative h-4 w-4 transition-transform duration-[var(--g-duration-micro)] group-hover:translate-x-1"
                />
              </Link>
              <Link
                href="/features"
                className="inline-flex items-center justify-center gap-2 rounded-full border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] px-7 py-3.5 text-sm font-semibold text-[color:var(--g-text-primary)] shadow-[var(--g-shadow-surface)] transition-all duration-[var(--g-duration-micro)] hover:border-[color:var(--g-border-active)] active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {MARKETING_COPY.hero.ctaSecondary}
              </Link>
            </motion.div>

            <motion.p
              initial={reduced ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: reduced ? 0 : 0.4, duration: 0.5 }}
              className={cn(TYPE_MARKETING.caption, "mt-5")}
            >
              {MARKETING_COPY.hero.benefitLine}
            </motion.p>
          </div>

          <motion.div
            initial={reduced ? false : { opacity: 0, y: 28 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.85, delay: reduced ? 0 : 0.2, ease }}
            className="relative"
          >
            <HybridHeroStage />
          </motion.div>
        </div>
      </motion.div>

      {!reduced ? (
        <div className="absolute bottom-8 left-1/2 flex -translate-x-1/2 flex-col items-center gap-2 text-[color:var(--g-text-muted)]">
          <span className="text-[10px] uppercase tracking-[0.28em]">Scroll</span>
          <motion.div
            className="h-8 w-px bg-gradient-to-b from-[color:var(--g-emerald)] to-transparent"
            animate={{ opacity: [0.35, 1, 0.35] }}
            transition={{ duration: timing.slow * 2, repeat: Infinity, ease: "easeInOut" }}
          />
        </div>
      ) : null}
    </section>
  )
}
