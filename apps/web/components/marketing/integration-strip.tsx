"use client"

import { motion } from "framer-motion"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { MARKETING_INTEGRATION_APPS } from "@/lib/connectors"
import { IntelligenceField } from "@/components/gravitre/visual"
import { useMotionPrefs } from "@/lib/animations"
import { cn } from "@/lib/utils"

export function IntegrationStrip() {
  const copy = MARKETING_COPY.integrationStrip
  const apps = MARKETING_INTEGRATION_APPS.slice(0, 14)
  const { reduced } = useMotionPrefs()
  const loop = [...apps, ...apps]

  return (
    <section className="relative overflow-hidden border-y border-border bg-muted/30 py-14">
      <IntelligenceField variant="section" atmosphere="systems" className="opacity-50" />
      <div className="relative mx-auto max-w-7xl px-6">
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="mb-2 text-center text-sm text-muted-foreground"
        >
          {copy.label}
        </motion.p>
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="mb-10 text-center text-xs text-muted-foreground"
        >
          {copy.note}
        </motion.p>

        {reduced ? (
          <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-6">
            {apps.map((name) => (
              <LogoCell key={name} name={name} />
            ))}
          </div>
        ) : (
          <div className="relative">
            <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-16 bg-gradient-to-r from-background to-transparent sm:w-24" />
            <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-16 bg-gradient-to-l from-background to-transparent sm:w-24" />
            <motion.div
              className="flex w-max gap-10"
              animate={{ x: ["0%", "-50%"] }}
              transition={{ duration: 42, ease: "linear", repeat: Infinity }}
            >
              {loop.map((name, i) => (
                <LogoCell key={`${name}-${i}`} name={name} hoverable />
              ))}
            </motion.div>
          </div>
        )}
      </div>
    </section>
  )
}

function LogoCell({ name, hoverable }: { name: string; hoverable?: boolean }) {
  return (
    <div
      className={cn(
        "flex min-w-[4.5rem] flex-col items-center gap-2 opacity-70 transition-all duration-[var(--g-duration-state)]",
        hoverable && "hover:opacity-100 hover:drop-shadow-[0_0_12px_color-mix(in_oklch,var(--g-signal)_35%,transparent)]",
      )}
    >
      <div className="rounded-xl border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)]/80 p-2.5 shadow-[var(--g-shadow-surface)] backdrop-blur-sm">
        <ConnectorIcon vendor={name} size="sm" />
      </div>
      <span className="text-[10px] font-medium tracking-wide text-muted-foreground">{name}</span>
    </div>
  )
}
