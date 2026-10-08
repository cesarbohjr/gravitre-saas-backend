import type { DocTier } from "@/lib/docs/types"

const TIER_STYLES: Record<DocTier, { label: string; className: string }> = {
  all: { label: "All plans", className: "border-border bg-muted text-muted-foreground" },
  free: { label: "Free", className: "border-border bg-muted text-muted-foreground" },
  node: { label: "Node", className: "border-info/30 bg-info/10 text-info" },
  control: { label: "Control", className: "border-brand/30 bg-brand-soft text-brand-text" },
  command: { label: "Command", className: "border-warning/30 bg-warning/10 text-warning-text" },
  enterprise: { label: "Enterprise", className: "border-foreground bg-foreground text-background" },
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
