"use client"

import Link from "next/link"
import { motion, useScroll, useTransform } from "framer-motion"
import { useRef } from "react"
import { ArrowRight, Play } from "lucide-react"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { useMotionPrefs, timing } from "@/lib/animations"
import { IntelligenceField } from "@/components/gravitre/visual"
import { ProductPreview } from "./product-preview"

/**
 * Marketing home first viewport (UI 2.0 Pilot A + Design Pass 2 material).
 * Budget: brand · one headline · one support · one CTA group · one dominant visual.
 * Layout locked — Intelligence Field upgrades atmosphere behind existing content.
 */
export function HeroParallax() {
  const heroRef = useRef(null)
  const { reduced } = useMotionPrefs()
  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ["start start", "end start"],
  })
  const heroOpacity = useTransform(scrollYProgress, [0, 0.5], [1, reduced ? 1 : 0])
  const heroScale = useTransform(scrollYProgress, [0, 0.5], [1, reduced ? 1 : 0.95])
  const heroY = useTransform(scrollYProgress, [0, 0.5], [0, reduced ? 0 : 100])

  return (
    <section
      ref={heroRef}
      className="relative flex min-h-[100svh] items-center justify-center bg-background text-foreground"
      data-marketing-hero=""
    >
      <IntelligenceField variant="hero" />

      <motion.div
        style={{ opacity: heroOpacity, scale: heroScale, y: heroY }}
        className="relative mx-auto max-w-7xl px-6 py-28 sm:py-36"
      >
        <div className="mx-auto max-w-4xl text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-primary">
            Gravitre
          </p>

          <h1 className="mt-5 text-5xl font-bold tracking-tight sm:text-7xl lg:text-8xl">
            <span className="block text-foreground">{MARKETING_COPY.hero.headline[0]}</span>
            <span className="mt-1 block bg-gradient-to-r from-primary via-[color:var(--g-intelligence)]/70 to-[color:var(--g-intelligence)] bg-clip-text text-transparent">
              {MARKETING_COPY.hero.headline[1]}
            </span>
          </h1>

          <p className="mx-auto mt-8 max-w-2xl text-lg leading-relaxed text-muted-foreground sm:text-xl">
            {MARKETING_COPY.hero.subhead}
          </p>

          <div className="mt-12 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link
              href="/get-started"
              className="group inline-flex items-center gap-2 rounded-full bg-primary px-8 py-4 text-base font-semibold text-primary-foreground transition-all duration-[var(--g-duration-micro)] hover:opacity-95 hover:shadow-[var(--g-glow-operational)] active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              <span>{MARKETING_COPY.hero.ctaPrimary}</span>
              <ArrowRight
                strokeWidth={1.5}
                className="h-5 w-5 transition-transform duration-[var(--g-duration-micro)] group-hover:translate-x-1"
              />
            </Link>
            <Link
              href="/features"
              className="group inline-flex items-center gap-2 rounded-full border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)]/80 px-8 py-4 text-base font-semibold text-foreground shadow-[var(--g-shadow-surface)] backdrop-blur-sm transition-all duration-[var(--g-duration-micro)] hover:border-[color:var(--g-border-active)] hover:bg-[color:var(--g-surface-2)] active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Play strokeWidth={1.5} className="h-5 w-5 fill-foreground" />
              <span>{MARKETING_COPY.hero.ctaSecondary}</span>
            </Link>
          </div>
        </div>

        <div className="mt-16 sm:mt-24">
          <ProductPreview />
        </div>
      </motion.div>

      {!reduced ? (
        <div className="absolute bottom-8 left-1/2 flex -translate-x-1/2 flex-col items-center gap-2 text-muted-foreground">
          <span className="text-xs uppercase tracking-widest">Scroll</span>
          <motion.div
            className="h-8 w-px bg-gradient-to-b from-muted-foreground to-transparent"
            animate={{ opacity: [0.4, 1, 0.4] }}
            transition={{ duration: timing.slow * 2, repeat: Infinity, ease: "easeInOut" }}
          />
        </div>
      ) : null}
    </section>
  )
}
