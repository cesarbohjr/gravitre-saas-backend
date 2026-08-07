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
      <div className="absolute -inset-4 rounded-2xl bg-gradient-to-b from-emerald-50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
      <div className="relative text-center">
        <div className="text-5xl sm:text-6xl font-bold text-zinc-900">
          {value}
          {suffix}
        </div>
        <div className="mt-2 text-sm text-zinc-500">{label}</div>
      </div>
    </div>
  )
}
