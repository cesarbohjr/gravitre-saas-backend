"use client"

import { cn } from "@/lib/utils"
import { forwardRef, type SVGProps } from "react"

interface NucleoIconProps extends Omit<SVGProps<SVGSVGElement>, 'ref'> {
  /** The numeric ID of the icon (e.g., "77487" for 77487.svg) */
  id: string
  /** Size in pixels (default: 24) */
  size?: number
}

/**
 * NucleoIcon - Renders a Nucleo premium icon from the public/icons/nucleo folder
 * 
 * Usage: <NucleoIcon id="77487" className="h-6 w-6" />
 * 
 * The icons are SVGs stored in public/icons/nucleo/{id}.svg
 */
export const NucleoIcon = forwardRef<HTMLImageElement, NucleoIconProps>(
  ({ id, className, size = 24, ...props }, ref) => {
    return (
      <img 
        ref={ref as React.Ref<HTMLImageElement>}
        src={`/icons/nucleo/${id}.svg`}
        alt=""
        aria-hidden="true"
        width={size}
        height={size}
        className={cn("inline-block shrink-0", className)}
        style={{ width: size, height: size }}
      />
    )
  }
)
NucleoIcon.displayName = "NucleoIcon"

/**
 * Creates a Nucleo icon component that can be used with React patterns expecting a component type.
 * 
 * Usage:
 * const RobotIcon = createNucleoIcon("77550")
 * <FeatureCard icon={RobotIcon} title="..." description="..." />
 */
export function createNucleoIcon(iconId: string) {
  const IconComponent = forwardRef<HTMLImageElement, Omit<NucleoIconProps, 'id'>>(
    ({ className, size = 24, ...props }, ref) => (
      <img 
        ref={ref as React.Ref<HTMLImageElement>}
        src={`/icons/nucleo/${iconId}.svg`}
        alt=""
        aria-hidden="true"
        width={size}
        height={size}
        className={cn("inline-block shrink-0", className)}
        style={{ width: size, height: size }}
      />
    )
  )
  IconComponent.displayName = `NucleoIcon_${iconId}`
  return IconComponent
}

/**
 * Semantic icon ID mappings for common use cases
 * These are curated and visually verified from the uploaded Nucleo icon set
 */
export const NucleoIcons = {
  // AI & Communication - VERIFIED
  edit: "77840",          // Edit/compose with pencil - great for AI writing
  checkCircle: "77860",   // Checkmark in circle - verified/success
  bezier: "77900",        // Bezier curve/connections - workflow/automation  
  store: "77920",         // Store/shop - business
  menu: "77940",          // Hamburger menu - navigation
  globe: "77960",         // Globe on stand - global/worldwide
  dashboard: "77980",     // Speedometer/gauge - performance/insights
  
  // Navigation & Actions - VERIFIED
  close: "77700",         // X close icon
  arrowUp: "77720",       // Arrow up in circle - growth/upload
  battery: "77740",       // Battery indicator
  search: "77760",        // Magnifying glass - search/discovery
  minus: "77780",         // Minus in square
  phone: "77800",         // Telephone - contact
  image: "77820",         // Image/photo
  inbox: "77880",         // Inbox/tray

  // Language & Translation - VERIFIED  
  translate: "78480",     // Translation icon (Chinese + A)
  
  // Solid Style Icons (78000+ range) - use for emphasis
  solidBezier: "78000",   // Solid bezier/tech
  solidDashboard: "78050", // Solid dashboard
  solidData: "78100",     // Solid data blocks
  solidGrid: "78150",     // Solid grid
  solidLayers: "78200",   // Solid layers
  solidShield: "78250",   // Solid shield
  solidLock: "78300",     // Solid lock
  solidCode: "78350",     // Solid code brackets
  solidBadge: "78400",    // Solid badge/check
  solidMessage: "78450",  // Solid message bubble
  
  // Legacy mappings for backwards compatibility
  robot: "77840",         // Using edit as proxy for AI
  brain: "77980",         // Using dashboard as proxy for intelligence
  sparkles: "77860",      // Using checkmark as proxy for magic
  workflow: "77900",      // Bezier - workflow connections
  shield: "78250",        // Solid shield
  lock: "78300",          // Solid lock  
  chart: "77980",         // Dashboard/speedometer
  users: "77800",         // Phone (placeholder)
  lightning: "77720",     // Arrow up as proxy for energy
  code: "78350",          // Solid code brackets
  rocket: "77720",        // Arrow up as proxy for launch
  target: "77860",        // Checkmark as proxy for target
  puzzle: "77900",        // Bezier as proxy for connections
  tools: "77840",         // Edit/pencil as proxy for tools  
  eye: "77760",           // Search/magnify as proxy for visibility
} as const

export type NucleoIconName = keyof typeof NucleoIcons

// Pre-created icon components for common use - VERIFIED ICONS
export const NucleoEditIcon = createNucleoIcon(NucleoIcons.edit)
export const NucleoCheckCircleIcon = createNucleoIcon(NucleoIcons.checkCircle)
export const NucleoBezierIcon = createNucleoIcon(NucleoIcons.bezier)
export const NucleoStoreIcon = createNucleoIcon(NucleoIcons.store)
export const NucleoGlobeIcon = createNucleoIcon(NucleoIcons.globe)
export const NucleoDashboardIcon = createNucleoIcon(NucleoIcons.dashboard)
export const NucleoSearchIcon = createNucleoIcon(NucleoIcons.search)
export const NucleoArrowUpIcon = createNucleoIcon(NucleoIcons.arrowUp)
export const NucleoPhoneIcon = createNucleoIcon(NucleoIcons.phone)
export const NucleoImageIcon = createNucleoIcon(NucleoIcons.image)
export const NucleoInboxIcon = createNucleoIcon(NucleoIcons.inbox)

// Solid style icon components
export const NucleoSolidShieldIcon = createNucleoIcon(NucleoIcons.solidShield)
export const NucleoSolidLockIcon = createNucleoIcon(NucleoIcons.solidLock)
export const NucleoSolidCodeIcon = createNucleoIcon(NucleoIcons.solidCode)
export const NucleoSolidBadgeIcon = createNucleoIcon(NucleoIcons.solidBadge)
export const NucleoSolidMessageIcon = createNucleoIcon(NucleoIcons.solidMessage)

// Legacy exports for backwards compatibility
export const NucleoRobotIcon = NucleoEditIcon
export const NucleoBrainIcon = NucleoDashboardIcon
export const NucleoSparklesIcon = NucleoCheckCircleIcon
export const NucleoWorkflowIcon = NucleoBezierIcon
export const NucleoShieldIcon = NucleoSolidShieldIcon
export const NucleoLockIcon = NucleoSolidLockIcon
export const NucleoChartIcon = NucleoDashboardIcon
export const NucleoUsersIcon = NucleoPhoneIcon
export const NucleoLightningIcon = NucleoArrowUpIcon
export const NucleoCodeIcon = NucleoSolidCodeIcon
export const NucleoRocketIcon = NucleoArrowUpIcon
export const NucleoTargetIcon = NucleoCheckCircleIcon
export const NucleoPuzzleIcon = NucleoBezierIcon
export const NucleoToolsIcon = NucleoEditIcon
export const NucleoEyeIcon = NucleoSearchIcon
