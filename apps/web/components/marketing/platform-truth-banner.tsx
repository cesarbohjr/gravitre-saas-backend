"use client"

import { motion } from "framer-motion"
import { MARKETING_COPY } from "@/lib/marketing-copy"

export function PlatformTruthBanner({ note }: { note?: string }) {
  return (
    <div className="py-12 border-y border-border bg-muted/50">
      <div className="mx-auto max-w-7xl px-6">
        {note ? (
          <p className="mb-8 text-center text-sm text-muted-foreground">{note}</p>
        ) : null}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          {MARKETING_COPY.stats.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className="text-center"
            >
              <div className="text-3xl md:text-4xl font-bold text-foreground">
                {stat.value}
                {"suffix" in stat ? stat.suffix : ""}
              </div>
              <div className="mt-1 text-sm text-muted-foreground">{stat.label}</div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  )
}

export function ProductTruthPills() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 1.2 }}
      className="flex flex-wrap items-center justify-center gap-3 mt-10 sm:mt-16 px-4"
    >
      {MARKETING_COPY.heroPills.map((pill, i) => (
        <motion.span
          key={pill.label}
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 1.3 + i * 0.08 }}
          className="rounded-full border border-primary/20 bg-card/90 px-4 py-2 text-sm font-medium text-primary shadow-sm"
        >
          {pill.label}
        </motion.span>
      ))}
    </motion.div>
  )
}
