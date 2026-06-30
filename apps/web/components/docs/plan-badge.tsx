import type { DocTier } from "@/lib/docs/types"

const TIER_STYLES: Record<DocTier, { label: string; className: string }> = {
  all: { label: "All plans", className: "border-zinc-200 bg-zinc-100 text-zinc-600" },
  free: { label: "Free", className: "border-zinc-200 bg-zinc-100 text-zinc-600" },
  node: { label: "Node", className: "border-sky-200 bg-sky-50 text-sky-700" },
  control: { label: "Control", className: "border-emerald-200 bg-emerald-50 text-emerald-700" },
  command: { label: "Command", className: "border-amber-200 bg-amber-50 text-amber-700" },
  enterprise: { label: "Enterprise", className: "border-zinc-700 bg-zinc-900 text-zinc-50" },
}

export function PlanBadge({ tier, label }: { tier: DocTier; label?: string }) {
  const style = TIER_STYLES[tier] ?? TIER_STYLES.all
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${style.className}`}
    >
      {label ?? style.label}
    </span>
  )
}
