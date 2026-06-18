import { getCategoryIcon, type AssetCategory } from "@/lib/marketplace-category-icons"
import { cn } from "@/lib/utils"

interface CategoryIconChipProps {
  assetType: AssetCategory
  department?: string | null
  // sm = 32px, md = 40px (matches the marketplace card icon footprint),
  // lg = 56px. Radius mirrors the card's existing `rounded-lg` chip.
  size?: "sm" | "md" | "lg"
  className?: string
}

const SIZE_MAP = { sm: 32, md: 40, lg: 56 } as const

export function CategoryIconChip({
  assetType,
  department,
  size = "md",
  className,
}: CategoryIconChipProps) {
  const config = getCategoryIcon(assetType, department)
  const Icon = config.icon
  const px = SIZE_MAP[size]
  const iconPx = Math.round(px * 0.5)

  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center rounded-lg",
        config.chipBg,
        config.chipBgDark,
        className,
      )}
      style={{ width: px, height: px }}
    >
      <Icon size={iconPx} weight="duotone" className={config.iconColor} aria-hidden />
    </div>
  )
}
