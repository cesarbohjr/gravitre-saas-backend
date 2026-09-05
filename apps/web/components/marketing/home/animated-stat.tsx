"use client"

export function AnimatedStat({
  value,
  label,
  suffix = "",
}: {
  value: string
  label: string
  suffix?: string
}) {
  // Static markup (no framer-motion) — homepage Lighthouse SI/TBT wins over entrance polish.
  return (
    <div className="relative group">
      <div className="absolute -inset-4 rounded-2xl bg-gradient-to-b from-[color:var(--g-intelligence)]/12 via-transparent to-[color:var(--g-emerald)]/8 opacity-0 transition-opacity duration-[var(--g-duration-state)] group-hover:opacity-100" />
      <div className="relative text-center">
        <div className="bg-gradient-to-b from-foreground to-foreground/80 bg-clip-text text-5xl font-bold tracking-tight text-transparent sm:text-6xl">
          {value}
          {suffix}
        </div>
        <div className="mt-2 text-sm text-muted-foreground">{label}</div>
      </div>
    </div>
  )
}
