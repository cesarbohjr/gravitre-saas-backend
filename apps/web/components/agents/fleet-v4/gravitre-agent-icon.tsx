"use client"

import { cn } from "@/lib/utils"
import { IDENTITY_COLOR_TOKENS, ROLE_ICON_REGISTRY } from "./identity-tokens"
import type { AgentIdentityColorId, AgentRoleIconId, AgentRuntimeState, IdentitySize } from "./types"
import { GravitreAgentStatusDot } from "./gravitre-agent-status"

const TILE_SIZE: Record<IdentitySize, string> = {
  sm: "h-8 w-8 rounded-[var(--np-radius-sm,6px)]",
  md: "h-9 w-9 rounded-[var(--np-radius-md,8px)]",
  lg: "h-12 w-12 rounded-[var(--np-radius-md,8px)]",
}

const ICON_PX: Record<IdentitySize, number> = {
  sm: 16,
  md: 18,
  lg: 22,
}

export interface GravitreAgentIconProps {
  icon: AgentRoleIconId
  identityColor: AgentIdentityColorId
  size?: IdentitySize
  runtimeState?: AgentRuntimeState
  showStatusDot?: boolean
  className?: string
  elevated?: boolean
}

/**
 * Uniform neutral tile for every agent; only the role glyph differs. The
 * user-chosen identity colour is kept as the glyph ink, not a tile fill.
 */
export function GravitreAgentIcon({
  icon,
  identityColor,
  size = "md",
  runtimeState,
  showStatusDot = false,
  className,
  elevated = false,
}: GravitreAgentIconProps) {
  const color = IDENTITY_COLOR_TOKENS[identityColor]
  const entry = ROLE_ICON_REGISTRY[icon] ?? ROLE_ICON_REGISTRY.general
  const { Icon } = entry

  return (
    <span
      className={cn(
        "relative inline-flex shrink-0 items-center justify-center border border-border bg-muted/60 transition-shadow dark:bg-[var(--graphite-800)]",
        TILE_SIZE[size],
        elevated && "shadow-[var(--np-shadow)]",
        className,
      )}
      aria-hidden
      data-agent-role={icon}
    >
      <Icon size={ICON_PX[size]} strokeWidth={1.75} className={color.iconClass} />
      {showStatusDot && runtimeState ? (
        <span className="absolute -bottom-0.5 -right-0.5">
          <GravitreAgentStatusDot state={runtimeState} />
        </span>
      ) : null}
    </span>
  )
}
