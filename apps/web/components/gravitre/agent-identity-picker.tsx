"use client"

import { cn } from "@/lib/utils"
import {
  AGENT_COLOR_OPTIONS,
  AGENT_ICON_OPTIONS,
  personalityFromAvatarColor,
  suggestAgentColor,
  suggestAgentIcon,
  type AgentAvatarColorId,
  type AgentIconId,
} from "@/lib/agent-identity"
import { LEGACY_COLOR_TO_IDENTITY, LEGACY_ICON_TO_ROLE } from "@/lib/agent-identity-bridge"
import { IDENTITY_COLOR_TOKENS, ROLE_ICON_REGISTRY } from "@/components/agents/fleet-v4/identity-tokens"
import { AgentIdentityAvatar } from "@/components/gravitre/agent-identity-avatar"

interface AgentIdentityPickerProps {
  name: string
  icon: AgentIconId
  avatarColor: AgentAvatarColorId
  onIconChange: (icon: AgentIconId) => void
  onColorChange: (color: AgentAvatarColorId) => void
  className?: string
}

/** Appearance picker — soft tiles + curated colors (API still stores legacy ids). */
export function AgentIdentityPicker({
  name,
  icon,
  avatarColor,
  onIconChange,
  onColorChange,
  className,
}: AgentIdentityPickerProps) {
  const personality = personalityFromAvatarColor(avatarColor)

  return (
    <div className={cn("space-y-4", className)}>
      <div className="flex items-center gap-4">
        <AgentIdentityAvatar
          identity={{
            name,
            icon,
            storedIcon: icon,
            avatarColor,
            avatarUrl: null,
            personality,
            initials: name.slice(0, 2).toUpperCase(),
          }}
          agent={{ name, icon, avatarColor, status: "active" }}
          size="lg"
          showStatusDot={false}
        />
        <div>
          <p className="text-sm font-medium text-foreground">Agent appearance</p>
          <p className="text-xs text-muted-foreground">
            Soft curated tiles only — no glow orbs, gradients, or freeform colors. Status stays a
            separate corner dot.
          </p>
        </div>
      </div>

      <div>
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Icon</p>
        <div className="grid grid-cols-4 gap-2 sm:grid-cols-6">
          {AGENT_ICON_OPTIONS.map((option) => {
            const roleId = LEGACY_ICON_TO_ROLE[option.id]
            const { Icon } = ROLE_ICON_REGISTRY[roleId]
            const selected = icon === option.id
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => onIconChange(option.id)}
                className={cn(
                  "flex flex-col items-center gap-1 rounded-[var(--np-radius-md)] border px-2 py-2 text-[10px] transition",
                  selected
                    ? "border-[color:var(--g-brand)] bg-[color:var(--g-brand-soft)]/40 text-foreground"
                    : "border-divide bg-[color:var(--g-surface-1)] text-muted-foreground hover:border-[color:var(--g-brand-border)]",
                )}
                aria-pressed={selected}
                title={option.label}
              >
                <Icon className="h-4 w-4" />
                <span className="truncate">{option.label}</span>
              </button>
            )
          })}
        </div>
      </div>

      <div>
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Color</p>
        <div className="flex flex-wrap gap-2">
          {AGENT_COLOR_OPTIONS.map((option) => {
            const selected = avatarColor === option.id
            const soft = IDENTITY_COLOR_TOKENS[LEGACY_COLOR_TO_IDENTITY[option.id]]
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => onColorChange(option.id)}
                className={cn(
                  "flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs transition",
                  selected
                    ? "border-[color:var(--g-brand)] bg-[color:var(--g-brand-soft)]/30 text-foreground"
                    : "border-divide text-muted-foreground hover:bg-[color:var(--g-surface-2)]",
                )}
                aria-pressed={selected}
              >
                <span
                  className={cn("h-4 w-4 rounded-sm border", soft.surfaceClass, soft.borderClass)}
                  aria-hidden
                />
                {option.label}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export function useSuggestedAgentIdentity(name: string, purpose?: string, department?: string) {
  const icon = suggestAgentIcon(name, purpose, null, department)
  const avatarColor = suggestAgentColor(icon, name, department)
  return { icon, avatarColor }
}
