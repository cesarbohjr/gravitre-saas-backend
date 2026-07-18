"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, Sparkles } from "lucide-react"
import { FEATURES_NAV, FEATURES_NAV_GROUPS } from "@/lib/features-nav"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { PlatformTruthBanner } from "@/components/marketing/platform-truth-banner"

export function FeaturesHub() {
  const cards = FEATURES_NAV.filter((item) => item.id !== "overview")

  return (
    <div className="relative overflow-hidden bg-white">
      <section className="relative overflow-hidden pt-28 pb-20 lg:pt-32">
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-50 via-transparent to-transparent" />
        <motion.div
          className="absolute top-0 left-1/2 h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-emerald-100/50 blur-3xl"
          animate={{ scale: [1, 1.1, 1], opacity: [0.35, 0.5, 0.35] }}
          transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
        />
        <div className="relative mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            className="mx-auto max-w-3xl text-center"
          >
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50/80 px-4 py-2">
              <Sparkles className="h-4 w-4 text-emerald-600" />
              <span className="text-sm font-medium text-emerald-700">{MARKETING_COPY.featuresHero.badge}</span>
            </div>
            <h1 className="text-4xl font-bold tracking-tight text-zinc-900 sm:text-5xl lg:text-6xl text-balance">
              {MARKETING_COPY.featuresHero.headline[0]}{" "}
              <span className="bg-gradient-to-r from-emerald-600 to-teal-500 bg-clip-text text-transparent">
                {MARKETING_COPY.featuresHero.headline[1]}
              </span>
            </h1>
            <p className="mt-6 text-lg text-zinc-600 text-pretty">{MARKETING_COPY.featuresHero.subtitle}</p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-2">
              {MARKETING_COPY.featuresHero.pills.map((pill) => (
                <span
                  key={pill}
                  className="rounded-full border border-zinc-200 bg-white/90 px-3 py-1.5 text-sm font-medium text-zinc-700 shadow-sm"
                >
                  {pill}
                </span>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      <PlatformTruthBanner note="Product mechanics we ship today — not customer counts or invented ROI." />

      <section className="py-20 lg:py-24">
        <div className="mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-2xl text-center mb-12">
            <h2 className="text-3xl font-bold tracking-tight text-zinc-900 sm:text-4xl">Explore by topic</h2>
            <p className="mt-4 text-zinc-600">
              Each area is its own page — platform capabilities, GIBE intelligence, governance, and honest metrics.
            </p>
          </div>

          {FEATURES_NAV_GROUPS.map((group, groupIndex) => (
            <div key={group} className={groupIndex > 0 ? "mt-14" : ""}>
              <p className="mb-5 text-xs font-semibold uppercase tracking-wider text-zinc-400">{group}</p>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {cards
                  .filter((item) => item.group === group)
                  .map((item, i) => {
                    const Icon = item.icon
                    return (
                      <motion.div
                        key={item.href}
                        initial={{ opacity: 0, y: 16 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: i * 0.05 }}
                      >
                        <Link
                          href={item.href}
                          className="group flex h-full flex-col rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm transition-all hover:-translate-y-0.5 hover:border-emerald-200 hover:shadow-md"
                        >
                          <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 ring-1 ring-emerald-100 transition-colors group-hover:bg-emerald-100">
                            <Icon className="h-5 w-5 text-emerald-700" />
                          </div>
                          <h3 className="text-lg font-semibold text-zinc-900">{item.label}</h3>
                          <p className="mt-2 flex-1 text-sm leading-relaxed text-zinc-600">{item.description}</p>
                          <span className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-emerald-700">
                            Explore
                            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                          </span>
                        </Link>
                      </motion.div>
                    )
                  })}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="border-t border-zinc-200 bg-zinc-50 py-16">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <h2 className="text-2xl font-bold text-zinc-900">Ready to run AI like an operator?</h2>
          <p className="mt-3 text-zinc-600">{MARKETING_COPY.cta.subtitle}</p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/get-started"
              className="inline-flex items-center gap-2 rounded-full bg-zinc-900 px-6 py-3 text-sm font-semibold text-white hover:bg-zinc-800"
            >
              Start free trial
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/contact"
              className="inline-flex items-center gap-2 rounded-full border border-zinc-300 bg-white px-6 py-3 text-sm font-semibold text-zinc-900 hover:bg-zinc-50"
            >
              Talk to sales
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}
