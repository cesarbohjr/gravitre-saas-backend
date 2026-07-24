"use client"

import Link from "next/link"
import { motion, useScroll, useTransform } from "framer-motion"
import { useRef } from "react"
import { ArrowRight, ChevronRight, Play } from "lucide-react"
import { ProductTruthPills } from "@/components/marketing/platform-truth-banner"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { GridBackground } from "./grid-background"
import { ProductPreview } from "./product-preview"

export function HeroParallax() {
  const heroRef = useRef(null)
  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ["start start", "end start"],
  })
  const heroOpacity = useTransform(scrollYProgress, [0, 0.5], [1, 0])
  const heroScale = useTransform(scrollYProgress, [0, 0.5], [1, 0.95])
  const heroY = useTransform(scrollYProgress, [0, 0.5], [0, 100])

  return (
    <section ref={heroRef} className="relative min-h-screen flex items-center justify-center">
      <GridBackground />

      <motion.div
        style={{ opacity: heroOpacity, scale: heroScale, y: heroY }}
        className="relative mx-auto max-w-7xl px-6 py-32 sm:py-40"
      >
        <div className="mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="mb-8 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50/80 backdrop-blur-sm px-4 py-2"
          >
            <motion.div
              className="h-2 w-2 rounded-full bg-emerald-500"
              animate={{ scale: [1, 1.3, 1], opacity: [1, 0.7, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
            <span className="text-sm font-medium text-emerald-700">{MARKETING_COPY.hero.badge}</span>
            <ChevronRight strokeWidth={1.5} className="h-4 w-4 text-emerald-500" />
          </motion.div>

          <div className="overflow-hidden">
            <motion.h1
              initial={{ opacity: 0, y: 60 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
              className="text-5xl sm:text-7xl lg:text-8xl font-bold tracking-tight"
            >
              <span className="text-zinc-900">{MARKETING_COPY.hero.headline[0]}</span>
            </motion.h1>
          </div>
          <div className="overflow-hidden">
            <motion.h1
              initial={{ opacity: 0, y: 60 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
              className="text-5xl sm:text-7xl lg:text-8xl font-bold tracking-tight"
            >
              <span className="bg-gradient-to-r from-emerald-600 via-emerald-500 to-teal-500 bg-clip-text text-transparent">
                {MARKETING_COPY.hero.headline[1]}
              </span>
            </motion.h1>
          </div>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.8 }}
            className="mt-8 text-lg sm:text-xl text-zinc-600 max-w-2xl mx-auto leading-relaxed"
          >
            {MARKETING_COPY.hero.subhead}
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1 }}
            className="mt-12 flex flex-col sm:flex-row items-center justify-center gap-4"
          >
            <Link
              href="/get-started"
              className="group inline-flex items-center gap-2 rounded-full bg-zinc-900 px-8 py-4 text-base font-semibold text-white transition-all hover:bg-zinc-800 hover:scale-[1.02] active:scale-[0.98]"
            >
              <span>Get Started Free</span>
              <ArrowRight strokeWidth={1.5} className="h-5 w-5 transition-transform group-hover:translate-x-1" />
            </Link>
            <Link
              href="/features"
              className="group inline-flex items-center gap-2 rounded-full border border-zinc-300 bg-white/80 backdrop-blur-sm px-8 py-4 text-base font-semibold text-zinc-900 shadow-sm transition-all hover:bg-white hover:border-zinc-400 hover:scale-[1.02] active:scale-[0.98]"
            >
              <motion.div animate={{ scale: [1, 1.1, 1] }} transition={{ duration: 2, repeat: Infinity }}>
                <Play strokeWidth={1.5} className="h-5 w-5 fill-zinc-900" />
              </motion.div>
              <span>See How It Works</span>
            </Link>
          </motion.div>

          <ProductTruthPills />
        </div>

        <motion.div
          initial={{ opacity: 0, y: 60 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1, duration: 0.8 }}
          className="mt-20 sm:mt-28"
        >
          <ProductPreview />
        </motion.div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.5 }}
        className="absolute bottom-8 left-1/2 -translate-x-1/2"
      >
        <motion.div
          animate={{ y: [0, 8, 0] }}
          transition={{ duration: 1.5, repeat: Infinity }}
          className="flex flex-col items-center gap-2 text-zinc-400"
        >
          <span className="text-xs uppercase tracking-widest">Scroll</span>
          <div className="h-8 w-px bg-gradient-to-b from-zinc-400 to-transparent" />
        </motion.div>
      </motion.div>
    </section>
  )
}
