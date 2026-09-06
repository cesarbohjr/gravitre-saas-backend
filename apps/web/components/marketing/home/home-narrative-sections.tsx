"use client"

/**
 * Progressive homepage narrative — Design Pass 3 one-brain story.
 * Illustrative demo only — no invented live ROI dollars.
 */

import { motion, AnimatePresence } from "framer-motion"
import { useEffect, useState } from "react"
import { Check } from "lucide-react"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { useMotionPrefs } from "@/lib/animations"
import { IntelligenceField } from "@/components/gravitre/visual"
import { cn } from "@/lib/utils"

const ease = [0.22, 1, 0.36, 1] as const

export function HomeNarrativeSections() {
  const n = MARKETING_COPY.homeNarrative
  const { reduced } = useMotionPrefs()

  return (
    <>
      {/* Problem */}
      <section className="relative border-t border-border py-28 sm:py-36" data-field-atmosphere="systems">
        <IntelligenceField variant="section" atmosphere="systems" className="opacity-18" />
        <div className="relative mx-auto max-w-3xl px-6 text-center">
          <p className="text-sm font-bold uppercase tracking-[0.22em] text-primary">{n.problem.eyebrow}</p>
          <h2 className="mt-5 text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
            {n.problem.title}
          </h2>
          <p className="mt-4 text-2xl font-semibold text-primary sm:text-3xl">{n.problem.subtitle}</p>
          <p className="mt-8 text-lg leading-relaxed text-muted-foreground">{n.problem.body}</p>
          <p className="mt-6 text-lg font-medium text-foreground">{n.problem.closer}</p>
        </div>
      </section>

      {/* One brain */}
      <section
        className="relative border-t border-border bg-card/30 py-28 sm:py-36"
        data-field-atmosphere="intelligence"
      >
        <IntelligenceField variant="section" atmosphere="intelligence" className="opacity-22" />
        <div className="relative mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-3xl text-center">
            <p className="text-sm font-bold uppercase tracking-[0.22em] text-primary">
              {n.oneBrain.eyebrow}
            </p>
            <h2 className="mt-5 text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
              {n.oneBrain.title}
            </h2>
            <p className="mt-6 text-lg leading-relaxed text-muted-foreground">{n.oneBrain.body}</p>
          </div>
          <OneBrainArchitecture reduced={reduced} />
        </div>
      </section>

      {/* Pillars */}
      <section className="relative border-t border-border py-28 sm:py-36" data-field-atmosphere="agents">
        <IntelligenceField variant="section" atmosphere="agents" className="opacity-16" />
        <div className="relative mx-auto max-w-7xl px-6">
          <div className="mx-auto mb-16 max-w-2xl text-center">
            <p className="text-sm font-bold uppercase tracking-[0.22em] text-primary">
              {n.pillars.eyebrow}
            </p>
            <h2 className="mt-5 text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
              {n.pillars.title}
            </h2>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            {n.pillars.items.map((item, i) => (
              <motion.div
                key={item.title}
                initial={reduced ? false : { opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-8%" }}
                transition={{ delay: i * 0.08, duration: 0.45, ease }}
                className="g-material-panel rounded-2xl border border-border p-7"
              >
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">
                  0{i + 1}
                </p>
                <h3 className="mt-4 text-xl font-bold text-foreground">{item.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{item.description}</p>
              </motion.div>
            ))}
          </div>
          <p className="mx-auto mt-12 max-w-2xl text-center text-sm font-medium text-muted-foreground">
            {n.pillars.governed}
          </p>
        </div>
      </section>

      {/* Tangible demo — illustrative */}
      <section
        className="relative border-t border-border bg-card/30 py-28 sm:py-36"
        data-field-atmosphere="outcome"
      >
        <IntelligenceField variant="section" atmosphere="outcome" className="opacity-18" />
        <div className="relative mx-auto max-w-7xl px-6">
          <div className="mx-auto mb-12 max-w-2xl text-center">
            <p className="text-sm font-bold uppercase tracking-[0.22em] text-amber-400">
              {n.demo.eyebrow}
            </p>
            <h2 className="mt-5 text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
              {n.demo.title}
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">{n.demo.subtitle}</p>
          </div>
          <IllustrativeDemo reduced={reduced} />
          <p className="mx-auto mt-8 max-w-xl text-center text-xs text-muted-foreground">
            {n.demo.footnote}
          </p>
        </div>
      </section>

      {/* Accountability */}
      <section className="relative border-t border-border py-28 sm:py-36" data-field-atmosphere="approval">
        <IntelligenceField variant="section" atmosphere="approval" className="opacity-16" />
        <div className="relative mx-auto max-w-4xl px-6 text-center">
          <p className="text-sm font-bold uppercase tracking-[0.22em] text-primary">
            {n.accountability.eyebrow}
          </p>
          <h2 className="mt-5 text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
            {n.accountability.title}
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">{n.accountability.subtitle}</p>
          <div className="mt-12 flex flex-wrap items-center justify-center gap-2">
            {n.accountability.stages.map((stage, i) => (
              <div key={stage} className="flex items-center gap-2">
                <span className="rounded-full border border-border bg-card px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-foreground">
                  {stage}
                </span>
                {i < n.accountability.stages.length - 1 ? (
                  <span className="text-muted-foreground">→</span>
                ) : (
                  <span className="text-primary">↺</span>
                )}
              </div>
            ))}
          </div>
          <p className="mt-10 text-base font-medium text-foreground">{n.accountability.closer}</p>
        </div>
      </section>

      {/* Simplification */}
      <section
        className="relative border-t border-border bg-card/30 py-28 sm:py-36"
        data-field-atmosphere="balanced"
      >
        <IntelligenceField variant="section" atmosphere="balanced" className="opacity-18" />
        <div className="relative mx-auto max-w-4xl px-6 text-center">
          <p className="text-sm font-bold uppercase tracking-[0.22em] text-primary">
            {n.simplification.eyebrow}
          </p>
          <h2 className="mt-5 text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
            {n.simplification.title}
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">{n.simplification.subtitle}</p>
          <div className="mx-auto mt-12 max-w-xl rounded-2xl border-2 border-primary/40 bg-background/80 p-8 shadow-[var(--g-glow-operational)]">
            <p className="text-sm font-bold uppercase tracking-[0.24em] text-primary">Gravitre</p>
            <ul className="mt-6 grid gap-3 sm:grid-cols-2">
              {n.simplification.layers.map((layer) => (
                <li
                  key={layer}
                  className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground"
                >
                  {layer}
                </li>
              ))}
            </ul>
          </div>
          <p className="mt-12 text-xl font-semibold text-foreground sm:text-2xl">
            {n.differentiation}
          </p>
          <p className="mt-4 text-sm text-muted-foreground">{n.categoryLine}</p>
        </div>
      </section>
    </>
  )
}

function OneBrainArchitecture({ reduced }: { reduced: boolean }) {
  const agents = ["Sales", "Marketing", "Finance", "HR", "Support", "IT"] as const
  return (
    <div className="mx-auto mt-16 max-w-3xl">
      <motion.div
        initial={reduced ? false : { opacity: 0, scale: 0.96 }}
        whileInView={{ opacity: 1, scale: 1 }}
        viewport={{ once: true }}
        className="mx-auto flex h-24 w-24 flex-col items-center justify-center rounded-full border-2 border-primary bg-background shadow-[var(--g-glow-operational)]"
      >
        <span className="text-[10px] font-bold uppercase tracking-widest text-primary">Brain</span>
        <span className="text-xs font-semibold text-foreground">Gravitre</span>
      </motion.div>
      <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {agents.map((agent, i) => (
          <motion.div
            key={agent}
            initial={reduced ? false : { opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.06, duration: 0.4, ease }}
            className="rounded-xl border border-border bg-card px-4 py-3 text-center"
          >
            <p className="text-sm font-semibold text-foreground">{agent} Agent</p>
            <p className="mt-1 text-[10px] text-muted-foreground">Shared context · own permissions</p>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

function IllustrativeDemo({ reduced }: { reduced: boolean }) {
  const demo = MARKETING_COPY.homeNarrative.demo
  const [step, setStep] = useState(0)

  useEffect(() => {
    if (reduced) {
      setStep(demo.steps.length)
      return
    }
    if (step >= demo.steps.length) return
    const t = setTimeout(() => setStep((s) => s + 1), 700)
    return () => clearTimeout(t)
  }, [step, reduced, demo.steps.length])

  return (
    <div className="mx-auto grid max-w-5xl gap-8 lg:grid-cols-2">
      <div className="rounded-2xl border border-border bg-background/90 p-6 shadow-[var(--g-shadow-elevated)]">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Ask</p>
        <p className="mt-3 text-lg font-medium text-foreground">&ldquo;{demo.prompt}&rdquo;</p>
        <ul className="mt-8 space-y-3">
          {demo.steps.map((label, i) => {
            const done = i < step
            return (
              <li key={label} className="flex items-center gap-3 text-sm">
                <span
                  className={cn(
                    "flex h-6 w-6 items-center justify-center rounded-full border",
                    done
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border text-transparent",
                  )}
                >
                  <Check className="h-3.5 w-3.5" strokeWidth={2.5} />
                </span>
                <span className={done ? "text-foreground" : "text-muted-foreground"}>{label}</span>
              </li>
            )
          })}
        </ul>
      </div>

      <div className="space-y-6">
        <AnimatePresence>
          {step >= demo.steps.length ? (
            <motion.div
              initial={reduced ? false : { opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-2xl border border-border bg-card p-6"
            >
              <p className="text-xs font-bold uppercase tracking-wide text-primary">
                {demo.findingsTitle}
              </p>
              <ul className="mt-4 space-y-2">
                {demo.findings.map((f) => (
                  <li key={f} className="text-sm font-medium text-foreground">
                    → {f}
                  </li>
                ))}
              </ul>
              <p className="mt-6 text-xs font-bold uppercase tracking-wide text-primary">
                {demo.actionsTitle}
              </p>
              <ul className="mt-3 space-y-2">
                {demo.actions.map((a) => (
                  <li key={a} className="flex items-center gap-2 text-sm text-foreground">
                    <Check className="h-4 w-4 text-primary" strokeWidth={2.5} />
                    {a}
                  </li>
                ))}
              </ul>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>
    </div>
  )
}
