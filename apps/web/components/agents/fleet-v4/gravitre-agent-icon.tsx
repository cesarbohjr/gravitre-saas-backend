"use client"

import { cn } from "@/lib/utils"
import { NUCLEO_SIZE } from "@/lib/design-system"
import { IDENTITY_COLOR_TOKENS, ROLE_ICON_REGISTRY } from "./identity-tokens"
import type { AgentIdentityColorId, AgentRoleIconId, AgentRuntimeState, IdentitySize } from "./types"
import { GravitreAgentStatusDot } from "./gravitre-agent-status"

const TILE_SIZE: Record<IdentitySize, string> = {
  sm: "h-9 w-9 rounded-[var(--np-radius-sm,6px)]",
  md: "h-11 w-11 rounded-[var(--np-radius-md,8px)]",
  lg: "h-14 w-14 rounded-[var(--np-radius-md,8px)]",
}

const ICON_PX: Record<IdentitySize, number> = {
  sm: NUCLEO_SIZE.row,
  md: NUCLEO_SIZE.secondary,
  lg: NUCLEO_SIZE.identity,
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
  const entry = ROLE_ICON_REGISTRY[icon] ?? ROLE_ICON_REGISTRY.general
  const { Icon } = entry

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
      <Icon size={ICON_PX[size]} className={color.iconClass} />
      {showStatusDot && runtimeState ? (
        <span className="absolute -bottom-0.5 -right-0.5">
          <GravitreAgentStatusDot state={runtimeState} />
        </span>
      ) : null}
    </span>
  )
}
