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
 * These are curated based on the uploaded Nucleo icon set
 */
export const NucleoIcons = {
  // AI & Automation (estimated based on icon ranges)
  robot: "77550",        // Robot/user icon
  brain: "77600",        // Intelligence  
  sparkles: "77650",     // Magic/AI
  wand: "77700",         // Magic wand/cross
  lightning: "77750",    // Activity/pulse chart
  
  // Workflow & Process
  workflow: "77800",     // Workflow/funnel
  blocks: "77850",       // Cloud/blocks
  layers: "77900",       // Layers/sliders
  flow: "77950",         // Flow/nodes
  cogs: "78000",         // Tree/hierarchy
  
  // Data & Analytics
  chart: "78050",        // Cart/data
  database: "78100",     // Layers/database
  graph: "78150",        // Grid/graph
  dashboard: "78200",    // Document/dashboard
  
  // Security & Trust
  shield: "78250",       // Download/secure
  lock: "78300",         // Lock/security
  key: "78350",          // Code/key
  checkmark: "78400",    // Badge/check
  
  // Communication
  message: "78450",      // Message
  bell: "78500",         // Bell/notification
  email: "77487",        // Email/photo
  send: "77490",         // Nature/send
  
  // Users & Teams  
  user: "77500",         // User/circle
  users: "77510",        // Multiple users
  building: "77520",     // Building
  globe: "77530",        // Globe
  
  // Development
  code: "77540",         // Code
  terminal: "77560",     // Terminal
  git: "77570",          // Git
  api: "77580",          // API
  
  // Time & Status
  clock: "77590",        // Clock
  calendar: "77610",     // Calendar
  refresh: "77620",      // Refresh
  play: "77630",         // Play
  
  // Objects
  document: "77640",     // Document
  folder: "77660",       // Folder
  cloud: "77670",        // Cloud
  server: "77680",       // Server
  
  // Navigation
  arrow: "77690",        // Arrow
  expand: "77710",       // Expand
  target: "77720",       // Target
  compass: "77730",      // Compass
  
  // Additional variety icons
  rocket: "77740",       // Rocket/launch
  star: "77760",         // Star/favorite
  heart: "77770",        // Heart/like
  flag: "77780",         // Flag/milestone
  award: "77790",        // Award/trophy
  puzzle: "77810",       // Puzzle/integration
  tools: "77820",        // Tools/settings
  eye: "77830",          // Eye/visibility
  search: "77840",       // Search
  filter: "77860",       // Filter
  sort: "77870",         // Sort
  download: "77880",     // Download
  upload: "77890",       // Upload
  link: "77910",         // Link
  share: "77920",        // Share
  bookmark: "77930",     // Bookmark
  tag: "77940",          // Tag
  pin: "77960",          // Pin/location
  map: "77970",          // Map
  home: "77980",         // Home
  settings: "77990",     // Settings
} as const

export type NucleoIconName = keyof typeof NucleoIcons

// Pre-created icon components for common use
export const NucleoRobotIcon = createNucleoIcon(NucleoIcons.robot)
export const NucleoBrainIcon = createNucleoIcon(NucleoIcons.brain)
export const NucleoSparklesIcon = createNucleoIcon(NucleoIcons.sparkles)
export const NucleoWorkflowIcon = createNucleoIcon(NucleoIcons.workflow)
export const NucleoShieldIcon = createNucleoIcon(NucleoIcons.shield)
export const NucleoLockIcon = createNucleoIcon(NucleoIcons.lock)
export const NucleoChartIcon = createNucleoIcon(NucleoIcons.chart)
export const NucleoUsersIcon = createNucleoIcon(NucleoIcons.users)
export const NucleoLightningIcon = createNucleoIcon(NucleoIcons.lightning)
export const NucleoGlobeIcon = createNucleoIcon(NucleoIcons.globe)
export const NucleoCodeIcon = createNucleoIcon(NucleoIcons.code)
export const NucleoRocketIcon = createNucleoIcon(NucleoIcons.rocket)
export const NucleoTargetIcon = createNucleoIcon(NucleoIcons.target)
export const NucleoPuzzleIcon = createNucleoIcon(NucleoIcons.puzzle)
export const NucleoToolsIcon = createNucleoIcon(NucleoIcons.tools)
export const NucleoEyeIcon = createNucleoIcon(NucleoIcons.eye)
