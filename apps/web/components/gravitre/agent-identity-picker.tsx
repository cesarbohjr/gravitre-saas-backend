"use client"

import { createElement } from "react"
import { cn } from "@/lib/utils"
import {
  AGENT_COLOR_OPTIONS,
  AGENT_ICON_OPTIONS,
  isAgentAvatarColorId,
  isAgentIconId,
  personalityFromAvatarColor,
  resolveAgentIconComponent,
  suggestAgentColor,
  suggestAgentIcon,
  type AgentAvatarColorId,
  type AgentIconId,
} from "@/lib/agent-identity"
import { AgentIdentityAvatar } from "@/components/gravitre/agent-identity-avatar"

interface AgentIdentityPickerProps {
  name: string
  icon: AgentIconId
  avatarColor: AgentAvatarColorId
  onIconChange: (icon: AgentIconId) => void
  onColorChange: (color: AgentAvatarColorId) => void
  className?: string
}

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
          size="lg"
        />
        <div>
          <p className="text-sm font-medium text-foreground">Agent appearance</p>
          <p className="text-xs text-muted-foreground">Used everywhere this agent appears.</p>
        </div>
      </div>

      <div>
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Icon</p>
        <div className="grid grid-cols-4 gap-2 sm:grid-cols-6">
          {AGENT_ICON_OPTIONS.map((option) => {
            const Icon = resolveAgentIconComponent(option.id)
            const selected = icon === option.id
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => onIconChange(option.id)}
                className={cn(
                  "flex flex-col items-center gap-1 rounded-xl border px-2 py-2 text-[10px] transition",
                  selected
                    ? "border-primary bg-primary/5 text-foreground"
                    : "border-border bg-card/50 text-muted-foreground hover:border-border/80 hover:bg-card",
                )}
                aria-pressed={selected}
                title={option.label}
              >
                {createElement(Icon, { className: "h-4 w-4", strokeWidth: 2 })}
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
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => onColorChange(option.id)}
                className={cn(
                  "flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs transition",
                  selected ? "border-primary bg-primary/5 text-foreground" : "border-border text-muted-foreground hover:bg-secondary",
                )}
                aria-pressed={selected}
              >
                <span className={cn("h-4 w-4 rounded-full", option.swatchClass)} aria-hidden />
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
