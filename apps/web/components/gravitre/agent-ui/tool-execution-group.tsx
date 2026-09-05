"use client"

/**
 * Agent Elements–inspired tool group (ADAPT).
 * Collapses consecutive tool chips into one quiet row while any are in-flight,
 * then expands to individual ToolChips. No AgentChat shell; Gravitre tokens only.
 */

import { useMemo, useState } from "react"
import { ChevronDown, Loader2, Wrench } from "lucide-react"
import { AnimatePresence, motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { RADIUS, STATUS, TYPE } from "@/lib/design-system"
import { ToolChip, type ToolInvocation } from "@/components/gravitre/assistant/tool-chip"

export function ToolExecutionGroup({
  invocations,
  className,
}: {
  invocations: ToolInvocation[]
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const running = useMemo(
    () => invocations.some((inv) => inv.state === "call"),
    [invocations],
  )
  const doneCount = invocations.filter((inv) => inv.state === "result").length
  const label = running
    ? `Running ${invocations.length} tool${invocations.length === 1 ? "" : "s"}…`
    : `${doneCount} tool${doneCount === 1 ? "" : "s"} completed`

  if (invocations.length === 0) return null

  if (invocations.length === 1) {
    return (
      <div className={cn("not-prose mb-2", className)}>
        <ToolChip invocation={invocations[0]} />
      </div>
    )
  }

  return (
    <div className={cn("not-prose mb-2", className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={cn(
          "inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium transition-colors",
          RADIUS.control,
          running ? STATUS.running : STATUS.idle,
        )}
      >
        {running ? (
          <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
        ) : (
          <Wrench className="h-3 w-3" aria-hidden />
        )}
        <span className={TYPE.meta}>{label}</span>
        <ChevronDown
          className={cn("h-3 w-3 transition-transform", open && "rotate-180")}
          aria-hidden
        />
      </button>
      <AnimatePresence initial={false}>
        {open || running ? (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-1 space-y-1 border-l border-border/60 pl-3">
              {invocations.map((invocation) => (
                <ToolChip key={invocation.toolCallId} invocation={invocation} />
              ))}
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  )
}
