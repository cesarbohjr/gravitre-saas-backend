import { getCategoryIcon, type AssetCategory } from "@/lib/marketplace-category-icons"
import { cn } from "@/lib/utils"

interface CategoryIconChipProps {
  assetType: AssetCategory
  department?: string | null
  title?: string
  size?: "sm" | "md" | "lg"
  className?: string
}

const SIZE_MAP = {
  sm: { box: "h-8 w-8", icon: 16 },
  md: { box: "h-9 w-9", icon: 18 },
  lg: { box: "h-12 w-12", icon: 22 },
} as const

/** Neutral asset mark: the same role glyphs and tile as agent identity. */
export function CategoryIconChip({
  assetType,
  department,
  title,
  size = "md",
  className,
}: CategoryIconChipProps) {
  const config = getCategoryIcon(assetType, department, title)
  const Icon = config.icon
  const dims = SIZE_MAP[size]

  return (
    <div
      role="img"
      aria-label={config.label}
      className={cn(
        "flex shrink-0 items-center justify-center rounded-[var(--np-radius-md,6px)] border border-border bg-muted/60 dark:bg-[var(--graphite-800)]",
        dims.box,
        className,
      )}
    >
      <Icon size={dims.icon} strokeWidth={1.75} className="text-[color:var(--g-text-secondary)]" aria-hidden />
    </div>
  )
}
