"use client"

/**
 * Canonical agent identity renderer (Agents 4.0 Phase 1).
 * Compact symbol tile — no glow discs, no saturated orbs.
 * Preserves prior API so call sites upgrade by import alone.
 */

import { cn } from "@/lib/utils"
import { GravitreAgentIcon } from "@/components/agents/fleet-v4/gravitre-agent-icon"
import { GravitreAgentStatusDot } from "@/components/agents/fleet-v4/gravitre-agent-status"
import {
  resolveAgentIdentity,
  type AgentIdentity,
  type AgentIdentityInput,
} from "@/lib/agent-identity"
import { resolveV4IdentityView } from "@/lib/agent-identity-bridge"
import type { AgentStatus } from "@/types/api"
import type { IdentitySize } from "@/components/agents/fleet-v4/types"

export type AgentIdentityAvatarSize = "xs" | "sm" | "md" | "lg" | "xl" | "orb"

const SIZE_TO_TILE: Record<AgentIdentityAvatarSize, IdentitySize> = {
  xs: "sm",
  sm: "sm",
  md: "md",
  lg: "lg",
  xl: "lg",
  /** Legacy orb size — now a large tile, not a 96px glow circle. */
  orb: "lg",
}

const FRAME: Record<AgentIdentityAvatarSize, string> = {
  xs: "h-6 w-6 rounded-[5px]",
  sm: "h-9 w-9 rounded-[var(--np-radius-sm,6px)]",
  md: "h-11 w-11 rounded-[var(--np-radius-md,8px)]",
  lg: "h-14 w-14 rounded-[var(--np-radius-md,8px)]",
  xl: "h-16 w-16 rounded-[var(--np-radius-md,8px)]",
  orb: "h-14 w-14 rounded-[var(--np-radius-md,8px)]",
}

export interface AgentIdentityAvatarProps {
  identity?: AgentIdentity
  agent?: AgentIdentityInput & { status?: AgentStatus | string | null }
  size?: AgentIdentityAvatarSize
  /** Prefer icon/color tile; initials only when explicitly requested and no photo. */
  showInitials?: boolean
  /** Show runtime status as a corner dot (never recolors the tile). */
  showStatusDot?: boolean
  className?: string
  iconClassName?: string
}

export function AgentIdentityAvatar({
  identity,
  agent,
  size = "md",
  showInitials = false,
  showStatusDot = true,
  className,
}: AgentIdentityAvatarProps) {
  const resolved = identity ?? resolveAgentIdentity(agent ?? {})
  const view = resolveV4IdentityView(agent ?? { name: resolved.name }, resolved)
  const useImage = Boolean(view.avatarUrl) && !showInitials
  const useInitials = showInitials && !useImage

  if (useImage || useInitials) {
    return (
      <span
        className={cn(
          "relative inline-flex shrink-0 items-center justify-center overflow-hidden border border-divide bg-[color:var(--g-surface-2)] text-[color:var(--g-text-primary)]",
          FRAME[size],
          className,
        )}
        title={view.name}
        aria-hidden={!showInitials}
      >
        {useImage ? (
          // eslint-disable-next-line @next/next/no-img-element -- agent avatars may be data URLs
          <img src={view.avatarUrl!} alt="" className="h-full w-full object-cover" />
        ) : (
          <span
            className={cn(
              "font-semibold tabular-nums",
              size === "xs" || size === "sm" ? "text-[9px]" : size === "md" ? "text-xs" : "text-sm",
            )}
          >
            {view.initials}
          </span>
        )}
        {showStatusDot && view.runtimeState ? (
          <span className="absolute -bottom-0.5 -right-0.5">
            <GravitreAgentStatusDot state={view.runtimeState} />
          </span>
        ) : null}
      </span>
    )
  }

  return (
    <GravitreAgentIcon
      icon={view.icon}
      identityColor={view.identityColor}
      size={SIZE_TO_TILE[size]}
      runtimeState={view.runtimeState}
      showStatusDot={showStatusDot && Boolean(view.runtimeState)}
      elevated={size === "lg" || size === "xl" || size === "orb"}
      className={cn(size === "xs" && FRAME.xs, size === "xl" && FRAME.xl, className)}
    />
  )
}
