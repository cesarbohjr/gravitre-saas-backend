"use client"

/**
 * Agent Elements–inspired thinking row (ADAPT).
 * Collapsible reasoning / status line mapped to real waiting copy — never invents CoT.
 */

import { useState } from "react"
import { ChevronDown } from "lucide-react"
import { AnimatePresence, motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { RADIUS, STATUS, TYPE } from "@/lib/design-system"
import { GravitreThinkingLoader } from "@/components/gravitre/assistant/thinking-loader"

export function ThinkingRow({
  label,
  detail,
  active = true,
  className,
}: {
  /** User-facing status from chat-agent-status / waiting label. */
  label: string
  /** Optional expanded detail (honest backend progress text only). */
  detail?: string | null
  active?: boolean
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const hasDetail = Boolean(detail?.trim())

  return (
    <div
      className={cn("not-prose", className)}
      role="status"
      aria-live="polite"
      aria-label={label}
    >
      <button
        type="button"
        disabled={!hasDetail}
        onClick={() => hasDetail && setOpen((v) => !v)}
        aria-expanded={hasDetail ? open : undefined}
        className={cn(
          "inline-flex max-w-full items-center gap-2 px-2.5 py-1 text-xs",
          RADIUS.control,
          active ? STATUS.running : STATUS.idle,
          hasDetail ? "cursor-pointer hover:opacity-90" : "cursor-default",
        )}
      >
        {active ? (
          <GravitreThinkingLoader size={14} title={label} className="text-current" />
        ) : null}
        <span className={cn(TYPE.meta, "truncate font-medium")}>{label}</span>
        {hasDetail ? (
          <ChevronDown
            className={cn("h-3 w-3 shrink-0 transition-transform", open && "rotate-180")}
            aria-hidden
          />
        ) : null}
      </button>
      <AnimatePresence initial={false}>
        {open && hasDetail ? (
          <motion.p
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-1 overflow-hidden pl-2 text-xs text-muted-foreground"
          >
            {detail}
          </motion.p>
        ) : null}
      </AnimatePresence>
    </div>
  )
}
