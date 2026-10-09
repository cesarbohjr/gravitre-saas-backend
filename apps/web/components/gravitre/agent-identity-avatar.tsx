"use client"

/**
 * Canonical agent identity renderer.
 * Every agent is drawn with its department's icon on the department tint
 * (lib/department-icons.ts); an uploaded photo still wins when one is set.
 * Preserves prior API so call sites upgrade by import alone.
 */

import { cn } from "@/lib/utils"
import { DepartmentIcon, type DepartmentIconSize } from "@/components/agents/department-icon"
import { GravitreAgentStatusDot } from "@/components/agents/fleet-v4/gravitre-agent-status"
import {
  resolveAgentIdentity,
  type AgentIdentity,
  type AgentIdentityInput,
} from "@/lib/agent-identity"
import { resolveV4IdentityView } from "@/lib/agent-identity-bridge"
import type { AgentStatus } from "@/types/api"

export type AgentIdentityAvatarSize = "xs" | "sm" | "md" | "lg" | "xl" | "orb"

const SIZE_TO_TILE: Record<AgentIdentityAvatarSize, DepartmentIconSize> = {
  xs: "xs",
  sm: "sm",
  md: "md",
  lg: "lg",
  xl: "xl",
  /** Legacy orb size — now a large tile, not a 96px glow circle. */
  orb: "lg",
}

const FRAME: Record<AgentIdentityAvatarSize, string> = {
  xs: "h-6 w-6 rounded-[5px]",
  sm: "h-8 w-8 rounded-[var(--np-radius-sm,6px)]",
  md: "h-9 w-9 rounded-[var(--np-radius-md,8px)]",
  lg: "h-12 w-12 rounded-[var(--np-radius-md,8px)]",
  xl: "h-14 w-14 rounded-[var(--np-radius-md,8px)]",
  orb: "h-12 w-12 rounded-[var(--np-radius-md,8px)]",
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
    <DepartmentIcon
      department={agent?.department}
      size={SIZE_TO_TILE[size]}
      className={cn((size === "lg" || size === "xl" || size === "orb") && "shadow-[var(--np-shadow)]", className)}
    >
      {showStatusDot && view.runtimeState ? (
        <span className="absolute -bottom-0.5 -right-0.5">
          <GravitreAgentStatusDot state={view.runtimeState} />
        </span>
      ) : null}
    </DepartmentIcon>
  )
}
