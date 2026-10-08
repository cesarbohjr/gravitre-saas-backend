"use client"

import { motion } from "framer-motion"
import { MARKETING_INTEGRATION_APPS } from "@/lib/connectors"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"

// Integration grid for the marketing pages. Every mark comes from the provider
// registry via ConnectorIcon, pinned to the light treatment because the
// marketing theme is always light. `theme` is retained for compatibility.
export function IntegrationsGrid(_props: { theme?: "light" | "dark" } = {}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.5 }}
      className="mx-auto grid max-w-5xl grid-cols-3 gap-x-4 gap-y-8 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6"
    >
      {MARKETING_INTEGRATION_APPS.map((name) => (
        <div
          key={name}
          title={name}
          className="group flex flex-col items-center justify-center gap-3"
        >
          <ConnectorIcon vendor={name} size="md" showStatusIndicator={false} forceLight />
          <span className="max-w-full truncate text-center text-xs font-medium text-muted-foreground transition-colors group-hover:text-foreground">
            {name}
          </span>
        </div>
      ))}
    </motion.div>
  )
}
