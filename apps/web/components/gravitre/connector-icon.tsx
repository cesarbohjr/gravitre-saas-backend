"use client"

import { cn } from "@/lib/utils"
import { hasProviderMark } from "@/lib/provider-registry"
import { ProviderLogo, type ProviderLogoSize } from "@/components/gravitre/provider-logo"

// ============================================================================
// GRAVITRE CONNECTOR ICON
// Thin wrapper over ProviderLogo: registry-resolved official mark in a fixed
// slot (no brand tile), plus an optional connection-status dot.
// ============================================================================

export const connectorIconSizes = {
  xs: { logo: "sm", slot: "h-5 w-5", dot: "h-1.5 w-1.5" },
  sm: { logo: "md", slot: "h-6 w-6", dot: "h-2 w-2" },
  md: { logo: "lg", slot: "h-7 w-7", dot: "h-2 w-2" },
} as const satisfies Record<string, { logo: ProviderLogoSize; slot: string; dot: string }>

export const connectorStatusTokens = {
  connected: {
    label: "Connected",
    dot: "bg-emerald-500",
    text: "text-emerald-600 dark:text-emerald-400",
    border: "border-emerald-200 dark:border-emerald-900/60",
    bg: "bg-emerald-50 dark:bg-emerald-950/30",
    ring: "ring-emerald-500/20",
  },
  syncing: {
    label: "Syncing",
    dot: "bg-blue-500",
    text: "text-blue-600 dark:text-blue-400",
    border: "border-blue-200 dark:border-blue-900/60",
    bg: "bg-blue-50 dark:bg-blue-950/30",
    ring: "ring-blue-500/20",
  },
  error: {
    label: "Error",
    dot: "bg-red-500",
    text: "text-red-600 dark:text-red-400",
    border: "border-red-200 dark:border-red-900/60",
    bg: "bg-red-50 dark:bg-red-950/30",
    ring: "ring-red-500/20",
  },
  disconnected: {
    label: "Disconnected",
    dot: "bg-zinc-400",
    text: "text-zinc-500 dark:text-zinc-400",
    border: "border-zinc-200 dark:border-zinc-800",
    bg: "bg-zinc-50 dark:bg-zinc-900/40",
    ring: "ring-zinc-500/10",
  },
  warning: {
    label: "Warning",
    dot: "bg-amber-500",
    text: "text-amber-600 dark:text-amber-400",
    border: "border-amber-200 dark:border-amber-900/60",
    bg: "bg-amber-50 dark:bg-amber-950/30",
    ring: "ring-amber-500/20",
  },
} as const

export type ConnectorStatus = keyof typeof connectorStatusTokens
export type ConnectorIconSize = keyof typeof connectorIconSizes

interface ConnectorIconProps {
  /** Connector display name (accessible-name fallback). */
  name?: string
  /** Vendor key, catalog type or provider id — resolved through the provider registry. */
  vendor?: string
  /** Custom icon for non-vendor items (e.g. generic data-source types). */
  icon?: React.ReactNode
  status?: ConnectorStatus
  size?: ConnectorIconSize
  selected?: boolean
  showStatusIndicator?: boolean
  className?: string
  onClick?: () => void
  /** Pin the light-theme logo treatment (always-light marketing surfaces). */
  forceLight?: boolean
}

/** True when ConnectorIcon renders an official brand mark (not the neutral fallback). */
export function hasConnectorBrandLogo(vendor?: string): boolean {
  return hasProviderMark(vendor)
}

export function ConnectorIcon({
  name,
  vendor,
  icon,
  status = "disconnected",
  size = "sm",
  selected = false,
  showStatusIndicator = true,
  className,
  onClick,
  forceLight = false,
}: ConnectorIconProps) {
  const statusToken = connectorStatusTokens[status] ?? connectorStatusTokens.disconnected
  const sizeToken = connectorIconSizes[size]
  const label = name || undefined

  return (
    <span
      className={cn(
        "relative inline-flex shrink-0 items-center justify-center rounded-md",
        sizeToken.slot,
        selected && "ring-1 ring-[var(--signal-500)]",
        onClick && "cursor-pointer",
        className,
      )}
      onClick={onClick}
    >
      {icon ? (
        <span role="img" aria-label={label ?? vendor ?? "Connector"} className="inline-flex items-center justify-center text-muted-foreground [&>svg]:h-[18px] [&>svg]:w-[18px]">
          {icon}
        </span>
      ) : (
        <ProviderLogo provider={vendor || name} label={label} size={sizeToken.logo} theme={forceLight ? "light" : "auto"} />
      )}
      {showStatusIndicator && status && (
        <span
          aria-hidden
          className={cn(
            "absolute -bottom-px -right-px rounded-full ring-2 ring-background",
            sizeToken.dot,
            statusToken.dot,
            status === "syncing" && "animate-pulse",
          )}
        />
      )}
    </span>
  )
}

interface ConnectorIconGridProps {
  connectors: Array<{ vendor: string; status?: ConnectorStatus }>
  size?: ConnectorIconSize
  maxVisible?: number
  className?: string
}

export function ConnectorIconGrid({ connectors, size = "xs", maxVisible = 4, className }: ConnectorIconGridProps) {
  const visible = connectors.slice(0, maxVisible)
  const remaining = connectors.length - maxVisible

  return (
    <div className={cn("flex items-center gap-1", className)}>
      {visible.map((connector, index) => (
        <ConnectorIcon
          key={`${connector.vendor}-${index}`}
          vendor={connector.vendor}
          status={connector.status}
          size={size}
          showStatusIndicator={false}
        />
      ))}
      {remaining > 0 && (
        <span className="font-mono text-[10px] tabular-nums text-muted-foreground">+{remaining}</span>
      )}
    </div>
  )
}

/** Neutral mark for connectors with no registry entry. */
export function ConnectorFallbackIcon({
  name,
  size = "sm",
  className,
}: {
  name: string
  size?: ConnectorIconSize
  className?: string
}) {
  return <ConnectorIcon name={name} vendor={name} size={size} showStatusIndicator={false} className={className} />
}
