import { getCategoryIcon, type AssetCategory } from "@/lib/marketplace-category-icons"
import { departmentGradient } from "@/lib/department-gradient"
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

  // Department packs render as a vivid gradient orb so they share the exact
  // color language of the Agents grid (same departmentGradient source).
  if (assetType === "department_pack") {
    const { gradient, glow } = departmentGradient(department)
    return (
      <div
        className={cn(
          "relative flex shrink-0 items-center justify-center rounded-full bg-gradient-to-br shadow-md",
          gradient,
          glow,
          className,
        )}
        style={{ width: px, height: px }}
      >
        {/* Glossy top highlight for depth, matching the agent orbs */}
        <span className="absolute inset-[2px] rounded-full bg-gradient-to-br from-white/25 to-transparent" aria-hidden />
        <Icon size={iconPx} weight="fill" className="relative z-10 text-white" aria-hidden />
      </div>
    )
  }

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
