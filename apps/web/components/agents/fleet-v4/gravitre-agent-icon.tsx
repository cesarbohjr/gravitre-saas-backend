"use client"

import { cn } from "@/lib/utils"
import { IDENTITY_COLOR_TOKENS, ROLE_ICON_REGISTRY } from "./identity-tokens"
import type { AgentIdentityColorId, AgentRoleIconId, AgentRuntimeState, IdentitySize } from "./types"
import { GravitreAgentStatusDot } from "./gravitre-agent-status"

const TILE_SIZE: Record<IdentitySize, string> = {
  sm: "h-9 w-9 rounded-[var(--np-radius-sm,6px)]",
  md: "h-11 w-11 rounded-[var(--np-radius-md,8px)]",
  lg: "h-14 w-14 rounded-[var(--np-radius-md,8px)]",
}

const ICON_SIZE: Record<IdentitySize, string> = {
  sm: "h-4 w-4",
  md: "h-[18px] w-[18px]",
  lg: "h-6 w-6",
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

/** Compact symbol tile — no glow discs, no saturated orbs. */
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
  const { Icon } = ROLE_ICON_REGISTRY[icon]

  return (
    <span
      className={cn(
        "relative inline-flex shrink-0 items-center justify-center border transition-shadow",
        TILE_SIZE[size],
        color.surfaceClass,
        color.borderClass,
        elevated && "shadow-[var(--np-shadow)]",
        className,
      )}
      aria-hidden
    >
      <Icon className={cn(ICON_SIZE[size], color.iconClass)} />
      {showStatusDot && runtimeState ? (
        <span className="absolute -bottom-0.5 -right-0.5">
          <GravitreAgentStatusDot state={runtimeState} />
        </span>
      ) : null}
    </span>
  )
}
