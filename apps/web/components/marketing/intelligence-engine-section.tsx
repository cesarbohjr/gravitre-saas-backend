"use client"

import { motion } from "framer-motion"
import { Brain, Cpu, Database, Layers, Network, Sparkles, Zap } from "lucide-react"
import { MARKETING_COPY } from "@/lib/marketing-copy"

const layerIcons = [Database, Brain, Cpu, Zap] as const

export function IntelligenceEngineSection({ variant = "default" }: { variant?: "default" | "compact" }) {
  const copy = MARKETING_COPY.intelligenceEngine
  const isCompact = variant === "compact"

  return (
    <section
      className={`relative border-t border-zinc-200 bg-white overflow-hidden ${isCompact ? "py-16 lg:py-20" : "py-24 lg:py-28"}`}
    >
      {!isCompact ? (
        <>
          <div className="absolute top-0 right-0 w-[480px] h-[480px] rounded-full bg-emerald-100/40 blur-3xl pointer-events-none" />
          <div className="absolute bottom-0 left-0 w-[360px] h-[360px] rounded-full bg-teal-100/30 blur-3xl pointer-events-none" />
        </>
      ) : null}

      <div className="relative mx-auto max-w-7xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className={`mx-auto max-w-3xl text-center ${isCompact ? "mb-10" : "mb-14"}`}
        >
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2">
            <Sparkles className="h-4 w-4 text-emerald-600" />
            <span className="text-sm font-medium text-emerald-700">{copy.badge}</span>
          </div>
          <h2
            className={`font-bold tracking-tight text-zinc-900 text-balance ${isCompact ? "text-3xl sm:text-4xl" : "text-4xl sm:text-5xl"}`}
          >
            {copy.title}
          </h2>
          <p className={`mt-3 text-zinc-600 text-pretty ${isCompact ? "text-base" : "text-lg"}`}>{copy.subtitle}</p>
          <p className="mt-2 text-sm font-medium text-emerald-700">{copy.tagline}</p>
        </motion.div>

        <div className={`grid gap-4 sm:grid-cols-2 lg:grid-cols-4 ${isCompact ? "mb-8" : "mb-10"}`}>
          {copy.layers.map((layer, i) => {
            const Icon = layerIcons[i] ?? Layers
            return (
              <motion.div
                key={layer.title}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.06 }}
                className="rounded-2xl border border-zinc-200 bg-zinc-50/80 p-5"
              >
                <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100">
                  <Icon className="h-5 w-5 text-emerald-700" />
                </div>
                <h3 className="text-base font-semibold text-zinc-900">{layer.title}</h3>
                <p className="mt-2 text-sm text-zinc-600 leading-relaxed">{layer.description}</p>
              </motion.div>
            )
          })}
        </div>

        {isCompact ? (
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mx-auto max-w-3xl rounded-xl border border-zinc-200 bg-zinc-50/80 px-5 py-4 text-sm leading-relaxed text-zinc-700"
          >
            <span className="font-semibold text-emerald-700">{copy.example.label}: </span>
            {copy.example.text}
          </motion.p>
        ) : (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="rounded-2xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-teal-50/80 p-6 md:p-8"
          >
            <div className="flex items-start gap-4">
              <div className="hidden sm:flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-white border border-emerald-200">
                <Network className="h-6 w-6 text-emerald-600" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">{copy.example.label}</p>
                <p className="mt-2 text-base text-zinc-800 leading-relaxed font-medium">{copy.example.text}</p>
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </section>
  )
}
