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
    dot: "bg-success",
    text: "text-success-text",
    border: "border-status-completed-border",
    bg: "bg-status-completed-bg",
    ring: "ring-success/20",
  },
  syncing: {
    label: "Syncing",
    dot: "bg-info",
    text: "text-info",
    border: "border-info/30",
    bg: "bg-info/10",
    ring: "ring-info/20",
  },
  error: {
    label: "Error",
    dot: "bg-destructive",
    text: "text-danger-text",
    border: "border-status-failed-border",
    bg: "bg-status-failed-bg",
    ring: "ring-destructive/20",
  },
  disconnected: {
    label: "Disconnected",
    dot: "bg-status-idle",
    text: "text-muted-foreground",
    border: "border-border",
    bg: "bg-muted",
    ring: "ring-border",
  },
  warning: {
    label: "Warning",
    dot: "bg-warning",
    text: "text-warning-text",
    border: "border-status-approval-border",
    bg: "bg-status-approval-bg",
    ring: "ring-warning/20",
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
