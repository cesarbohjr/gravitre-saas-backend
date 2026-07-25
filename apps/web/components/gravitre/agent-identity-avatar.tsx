"use client"

import { createElement } from "react"
import { cn } from "@/lib/utils"
import {
  resolveAgentIconComponent,
  resolveAgentIdentity,
  type AgentIdentity,
  type AgentIdentityInput,
} from "@/lib/agent-identity"

export type AgentIdentityAvatarSize = "xs" | "sm" | "md" | "lg" | "xl" | "orb"

const sizeClasses: Record<AgentIdentityAvatarSize, string> = {
  xs: "h-6 w-6 rounded-lg",
  sm: "h-8 w-8 rounded-xl",
  md: "h-10 w-10 rounded-xl",
  lg: "h-12 w-12 rounded-2xl",
  xl: "h-20 w-20 sm:h-24 sm:w-24 rounded-2xl",
  orb: "h-24 w-24 rounded-2xl",
}

const iconSizeClasses: Record<AgentIdentityAvatarSize, string> = {
  xs: "h-3 w-3",
  sm: "h-4 w-4",
  md: "h-5 w-5",
  lg: "h-6 w-6",
  xl: "h-10 w-10 sm:h-11 sm:w-11",
  orb: "h-10 w-10",
}

const initialsSizeClasses: Record<AgentIdentityAvatarSize, string> = {
  xs: "text-[9px]",
  sm: "text-[10px]",
  md: "text-xs",
  lg: "text-sm",
  xl: "text-2xl sm:text-3xl",
  orb: "text-xl",
}

export interface AgentIdentityAvatarProps {
  identity?: AgentIdentity
  agent?: AgentIdentityInput
  size?: AgentIdentityAvatarSize
  showInitials?: boolean
  className?: string
  iconClassName?: string
}

export function AgentIdentityAvatar({
  identity,
  agent,
  size = "md",
  showInitials = false,
  className,
  iconClassName,
}: AgentIdentityAvatarProps) {
  const resolved = identity ?? resolveAgentIdentity(agent ?? {})
  const Icon = resolveAgentIconComponent(resolved.icon, agent?.role, resolved.name)
  const useInitials = showInitials

  return (
    <div
      className={cn(
        "relative flex shrink-0 items-center justify-center bg-gradient-to-br text-white shadow-md",
        sizeClasses[size],
        resolved.personality.gradient,
        resolved.personality.glow,
        className,
      )}
      aria-hidden={!showInitials}
      title={resolved.name}
    >
      <div className="pointer-events-none absolute inset-0 rounded-[inherit] bg-gradient-to-br from-white/20 to-transparent" />
      {useInitials ? (
        <span className={cn("relative z-10 font-bold", initialsSizeClasses[size])}>{resolved.initials}</span>
      ) : (
        createElement(Icon, {
          className: cn("relative z-10 drop-shadow", iconSizeClasses[size], iconClassName),
          strokeWidth: 2,
        })
      )}
    </div>
  )
}
