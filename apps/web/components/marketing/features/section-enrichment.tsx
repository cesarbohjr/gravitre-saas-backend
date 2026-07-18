"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight } from "lucide-react"
import type { FeaturesSectionId } from "@/lib/features-nav"
import {
  getSectionContent,
  type Capability,
  type FlowStep,
  type Spec,
} from "@/lib/features-sections-content"

const EASE = [0.16, 1, 0.3, 1] as const

/* -------------------------------------------------------------------------- */
/* Takeaway — a single, confident line under the primary showcase             */
/* -------------------------------------------------------------------------- */
export function FeatureTakeaway({ text }: { text: string }) {
  return (
    <section className="border-t border-zinc-200 bg-zinc-50/60">
      <div className="mx-auto max-w-4xl px-6 py-14 text-center">
        <motion.p
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5, ease: EASE }}
          className="text-xl font-medium leading-relaxed text-zinc-800 text-balance sm:text-2xl"
        >
          {text}
        </motion.p>
      </div>
    </section>
  )
}

/* -------------------------------------------------------------------------- */
/* Flow diagram — animated numbered pipeline with a traveling pulse           */
/* -------------------------------------------------------------------------- */
export function FeatureFlowDiagram({
  title,
  note,
  steps,
}: {
  title: string
  note?: string
  steps: FlowStep[]
}) {
  return (
    <section className="py-20 lg:py-24">
      <div className="mx-auto max-w-6xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5, ease: EASE }}
          className="mx-auto max-w-2xl text-center"
        >
          <h2 className="text-2xl font-bold tracking-tight text-zinc-900 sm:text-3xl text-balance">{title}</h2>
          {note ? <p className="mt-3 text-zinc-600 text-pretty">{note}</p> : null}
        </motion.div>

        <div className="relative mt-14">
          {/* connective track (desktop) */}
          <div className="pointer-events-none absolute left-0 right-0 top-7 hidden lg:block">
            <div className="relative mx-auto h-0.5 w-[85%] overflow-hidden rounded-full bg-zinc-200">
              <motion.div
                className="absolute inset-y-0 left-0 w-1/3 rounded-full bg-gradient-to-r from-transparent via-emerald-400 to-transparent"
                animate={{ x: ["-40%", "320%"] }}
                transition={{ duration: 3.4, repeat: Infinity, ease: "easeInOut" }}
              />
            </div>
          </div>

          <ol className="relative grid gap-8 sm:grid-cols-2 lg:flex lg:items-start lg:justify-between lg:gap-4">
            {steps.map((step, i) => (
              <motion.li
                key={step.label}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 0.45, delay: i * 0.1, ease: EASE }}
                className="relative flex flex-col items-center text-center lg:w-full lg:max-w-[180px]"
              >
                <div className="relative">
                  <motion.span
                    className="absolute inset-0 rounded-2xl bg-emerald-400/30"
                    animate={{ scale: [1, 1.35, 1], opacity: [0.4, 0, 0.4] }}
                    transition={{ duration: 3, repeat: Infinity, delay: i * 0.4 }}
                  />
                  <span className="relative flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-emerald-600 text-lg font-bold text-white shadow-lg shadow-emerald-500/20">
                    {i + 1}
                  </span>
                </div>
                <span className="mt-4 text-sm font-semibold text-zinc-900">{step.label}</span>
                <span className="mt-1 text-xs leading-snug text-zinc-500">{step.sub}</span>
              </motion.li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  )
}

/* -------------------------------------------------------------------------- */
/* Capability grid — 2x2 cards with hover lift                                */
/* -------------------------------------------------------------------------- */
export function FeatureCapabilityGrid({
  title,
  items,
}: {
  title: string
  items: Capability[]
}) {
  return (
    <section className="border-t border-zinc-200 bg-white py-20 lg:py-24">
      <div className="mx-auto max-w-6xl px-6">
        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5, ease: EASE }}
          className="mb-10 text-center text-2xl font-bold tracking-tight text-zinc-900 sm:text-3xl"
        >
          {title}
        </motion.h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {items.map((item, i) => {
            const Icon = item.icon
            return (
              <motion.div
                key={item.title}
                initial={{ opacity: 0, y: 18 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 0.45, delay: i * 0.06, ease: EASE }}
                className="group flex gap-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm transition-all hover:-translate-y-0.5 hover:border-emerald-200 hover:shadow-md"
              >
                <div className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-50 ring-1 ring-emerald-100 transition-colors group-hover:bg-emerald-100">
                  <Icon className="h-5 w-5 text-emerald-700" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-zinc-900">{item.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-zinc-600">{item.desc}</p>
                </div>
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  )
}

/* -------------------------------------------------------------------------- */
/* Spec strip — a compact row of headline numbers                             */
/* -------------------------------------------------------------------------- */
export function FeatureSpecStrip({ specs }: { specs: Spec[] }) {
  return (
    <section className="border-t border-zinc-200 bg-zinc-50">
      <div className="mx-auto grid max-w-4xl grid-cols-1 divide-y divide-zinc-200 px-6 py-4 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        {specs.map((spec, i) => (
          <motion.div
            key={spec.label}
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-40px" }}
            transition={{ duration: 0.4, delay: i * 0.08, ease: EASE }}
            className="flex flex-col items-center py-6 text-center"
          >
            <span className="text-3xl font-bold tracking-tight text-zinc-900">{spec.value}</span>
            <span className="mt-1 text-xs font-medium uppercase tracking-wider text-zinc-500">{spec.label}</span>
          </motion.div>
        ))}
      </div>
    </section>
  )
}

/* -------------------------------------------------------------------------- */
/* Section CTA — focused, per-page call to action                            */
/* -------------------------------------------------------------------------- */
export function FeatureSectionCTA({ label }: { label: string }) {
  return (
    <section className="border-t border-zinc-200 bg-white py-16">
      <div className="mx-auto max-w-3xl px-6 text-center">
        <h2 className="text-2xl font-bold tracking-tight text-zinc-900 text-balance">{label}</h2>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
          <Link
            href="/get-started"
            className="inline-flex items-center gap-2 rounded-full bg-zinc-900 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-zinc-800"
          >
            Start free trial
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            href="/contact"
            className="inline-flex items-center gap-2 rounded-full border border-zinc-300 bg-white px-6 py-3 text-sm font-semibold text-zinc-900 transition-colors hover:bg-zinc-50"
          >
            Talk to sales
          </Link>
        </div>
      </div>
    </section>
  )
}

/* -------------------------------------------------------------------------- */
/* Composed enrichment for a section — pulls from the content config          */
/* -------------------------------------------------------------------------- */
export function FeatureEnrichment({ sectionId }: { sectionId: FeaturesSectionId }) {
  const content = getSectionContent(sectionId)
  if (!content) return null

  return (
    <>
      <FeatureTakeaway text={content.takeaway} />
      <FeatureFlowDiagram title={content.flowTitle} note={content.flowNote} steps={content.flow} />
      <FeatureCapabilityGrid title={content.capabilitiesTitle} items={content.capabilities} />
      <FeatureSpecStrip specs={content.specs} />
    </>
  )
}
