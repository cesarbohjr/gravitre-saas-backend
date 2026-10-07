import { CERTAINTY_LABEL, type Certainty } from "@/components/intelligence/impact/impact-model"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

/** Filled dot = measured, ring = estimated, dash = no evidence yet. */
export function CertaintyMarker({ certainty, className }: { certainty: Certainty; className?: string }) {
  const label = CERTAINTY_LABEL[certainty]
  return (
    <span
      role="img"
      aria-label={label}
      title={label}
      className={cn("inline-flex h-3 w-3 shrink-0 items-center justify-center", className)}
    >
      {certainty === "measured" ? (
        <span className="h-2.5 w-2.5 rounded-full bg-[color:var(--g-brand)]" />
      ) : certainty === "estimated" ? (
        <span className="h-2.5 w-2.5 rounded-full border-2 border-[color:var(--g-warning)]" />
      ) : (
        <span className="h-0.5 w-2.5 rounded-full bg-[color:var(--g-text-muted)]" />
      )}
    </span>
  )
}

export function CertaintyLegend() {
  return (
    <div
      className="flex flex-wrap items-center gap-x-5 gap-y-2"
      role="group"
      aria-label="How sure is each number"
    >
      <span className={cn(TYPE.eyebrow, "uppercase tracking-[0.08em]")}>How sure is each number</span>
      {(["measured", "estimated", "none"] as const).map((c) => (
        <span key={c} className="inline-flex items-center gap-1.5 text-[13px] text-[color:var(--g-text-primary)]">
          <CertaintyMarker certainty={c} />
          <span aria-hidden>{CERTAINTY_LABEL[c]}</span>
        </span>
      ))}
    </div>
  )
}
