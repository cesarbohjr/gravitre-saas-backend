"use client"

import { cn } from "@/lib/utils"
import { GravitreAgentIcon } from "./gravitre-agent-icon"
import type {
  AgentIdentityColorId,
  AgentRoleIconId,
  AgentRuntimeState,
  IdentitySize,
  IdentityVariant,
} from "./types"

export interface GravitreAgentIdentityProps {
  icon: AgentRoleIconId
  identityColor: AgentIdentityColorId
  status?: AgentRuntimeState
  size?: IdentitySize
  variant?: IdentityVariant
  className?: string
}

/**
 * Canonical agent identity API — one source for row / card / graph / picker.
 * Status is a tiny overlay; never recolors the tile.
 */
export function GravitreAgentIdentity({
  icon,
  identityColor,
  status,
  size,
  variant = "card",
  className,
}: GravitreAgentIdentityProps) {
  const resolvedSize: IdentitySize =
    size ?? (variant === "row" || variant === "graph" ? "sm" : variant === "picker" ? "lg" : "md")

  return (
    <GravitreAgentIcon
      icon={icon}
      identityColor={identityColor}
      size={resolvedSize}
      runtimeState={status}
      showStatusDot={Boolean(status)}
      elevated={variant === "card" || variant === "picker"}
      className={cn(className)}
    />
  )
}
