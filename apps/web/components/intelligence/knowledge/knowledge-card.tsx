/**
 * The Knowledge design's section card: an 18px-radius white panel with a
 * title row (title, optional lead, optional right-hand slot) above its body.
 * Inner cards and tiles use KNOWLEDGE_TILE (14px) and KNOWLEDGE_STAT (12px).
 */
import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

export const KNOWLEDGE_CARD =
  "rounded-[18px] border border-divide bg-[color:var(--g-surface-1)] shadow-[var(--np-shadow)]"
export const KNOWLEDGE_TILE = "rounded-[14px]"
export const KNOWLEDGE_STAT = "rounded-[12px]"

export function KnowledgeCard({
  id,
  title,
  titleSize = "md",
  lead,
  aside,
  children,
  className,
  bodyClassName,
  padded = true,
}: {
  id: string
  title: ReactNode
  /** lg = 18px (the page's lead card), md = 16px. */
  titleSize?: "lg" | "md"
  lead?: ReactNode
  aside?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
  /** false lets a full-bleed body (graph canvas, table) touch the card edge. */
  padded?: boolean
}) {
  return (
    <section aria-labelledby={id} className={cn(KNOWLEDGE_CARD, padded ? "p-5 sm:p-6" : "overflow-hidden", className)}>
      <div className={cn("flex flex-wrap items-start justify-between gap-3", !padded && "p-5 pb-0 sm:p-6 sm:pb-0")}>
        <div className="min-w-0 space-y-1">
          <h2
            id={id}
            className={cn(
              "font-semibold text-[color:var(--g-text-primary)]",
              titleSize === "lg" ? "text-lg" : "text-base",
            )}
          >
            {title}
          </h2>
          {lead ? <p className="text-sm text-[color:var(--g-text-secondary)]">{lead}</p> : null}
        </div>
        {aside}
      </div>
      <div className={cn("mt-4", bodyClassName)}>{children}</div>
    </section>
  )
}
