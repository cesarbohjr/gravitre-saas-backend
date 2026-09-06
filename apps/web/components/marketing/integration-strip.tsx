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
    <section className="relative overflow-hidden border-y border-border bg-card/40 py-16">
      <IntelligenceField variant="section" atmosphere="systems" className="opacity-30" />
      <div className="relative mx-auto max-w-7xl px-6">
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="mb-2 text-center text-sm font-semibold text-foreground"
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
            <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-16 bg-gradient-to-r from-background to-transparent sm:w-28" />
            <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-16 bg-gradient-to-l from-background to-transparent sm:w-28" />
            <motion.div
              className="flex w-max gap-10"
              animate={{ x: ["0%", "-50%"] }}
              transition={{ duration: 36, ease: "linear", repeat: Infinity }}
            >
              {loop.map((name, i) => (
                <LogoCell key={`${name}-${i}`} name={name} hoverable animatedIndex={i} />
              ))}
            </motion.div>
          </div>
        )}
      </div>
    </section>
  )
}

function LogoCell({
  name,
  hoverable,
  animatedIndex = 0,
}: {
  name: string
  hoverable?: boolean
  animatedIndex?: number
}) {
  return (
    <motion.div
      className={cn(
        "group flex min-w-[4.75rem] flex-col items-center gap-2",
        hoverable && "cursor-default",
      )}
      animate={
        hoverable
          ? { y: [0, -4, 0] }
          : undefined
      }
      transition={
        hoverable
          ? {
              duration: 3.2,
              delay: (animatedIndex % 7) * 0.35,
              repeat: Infinity,
              ease: "easeInOut",
            }
          : undefined
      }
    >
      <div
        className={cn(
          "rounded-xl border border-border bg-zinc-50 p-2.5 shadow-[var(--g-shadow-surface)] transition-transform duration-[var(--g-duration-state)]",
          hoverable && "group-hover:scale-110 group-hover:border-primary/50 group-hover:shadow-[var(--g-glow-operational)]",
        )}
      >
        <ConnectorIcon vendor={name} size="sm" forceLight showStatusIndicator={false} />
      </div>
      <span className="text-[10px] font-semibold tracking-wide text-muted-foreground group-hover:text-foreground">
        {name}
      </span>
    </motion.div>
  )
}
