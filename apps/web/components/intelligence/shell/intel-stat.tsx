import type { ReactNode } from "react"
import { INTEL } from "@/components/intelligence/shell/intel-ui"
import { cn } from "@/lib/utils"

/** Stat card from the Intelligence designs: label, 28px value, one-line hint. */
export function IntelStat({
  label,
  value,
  hint,
  valueClassName,
}: {
  label: ReactNode
  value: ReactNode
  hint?: ReactNode
  valueClassName?: string
}) {
  const wordy = typeof value === "string" && !/^[\d$≈~.,%\s—–-]+[a-zA-Z]{0,3}$/.test(value)
  return (
    <div className={INTEL.stat}>
      <span className={INTEL.statLabel}>{label}</span>
      <span className={cn(INTEL.statValue, wordy && "pt-1.5 text-[20px] leading-8", valueClassName)}>{value}</span>
      {hint ? <span className={INTEL.statHint}>{hint}</span> : null}
    </div>
  )
}
