"use client"

import { motion } from "framer-motion"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { MARKETING_INTEGRATION_APPS } from "@/lib/connectors"

export function IntegrationStrip() {
  const copy = MARKETING_COPY.integrationStrip
  const apps = MARKETING_INTEGRATION_APPS.slice(0, 12)

  return (
    <section className="relative border-y border-zinc-200 bg-zinc-50 py-12">
      <div className="mx-auto max-w-7xl px-6">
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="text-center text-sm text-zinc-500 mb-2"
        >
          {copy.label}
        </motion.p>
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="text-center text-xs text-zinc-400 mb-8"
        >
          {copy.note}
        </motion.p>
        <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-6">
          {apps.map((name, i) => (
            <motion.div
              key={name}
              initial={{ opacity: 0, y: 8 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.04 }}
              className="flex flex-col items-center gap-2"
            >
              <ConnectorIcon vendor={name} size="sm" />
              <span className="text-xs font-medium text-zinc-500">{name}</span>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
