"use client"

import { useState } from "react"
import { cn } from "@/lib/utils"
import { IDENTITY_COLOR_TOKENS, ROLE_ICON_REGISTRY, suggestRoleIcon } from "./identity-tokens"
import { GravitreAgentIdentity } from "./gravitre-agent-identity"
import type { AgentIdentityColorId, AgentRoleIconId } from "./types"

const ICON_IDS = Object.keys(ROLE_ICON_REGISTRY) as AgentRoleIconId[]
const COLOR_IDS = Object.keys(IDENTITY_COLOR_TOKENS) as AgentIdentityColorId[]

export function AgentAppearancePicker({
  roleHint = "Platform Reliability Analyst",
  className,
}: {
  roleHint?: string
  className?: string
}) {
  const suggested = suggestRoleIcon(roleHint)
  const [icon, setIcon] = useState<AgentRoleIconId>(suggested)
  const [color, setColor] = useState<AgentIdentityColorId>("teal")

  return (
    <div
      className={cn(
        "max-w-lg space-y-5 rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-5 shadow-[var(--np-shadow)]",
        className,
      )}
    >
      <div>
        <h3 className="text-sm font-semibold text-[color:var(--g-text-primary)]">
          Agent appearance
        </h3>
        <p className="mt-1 text-xs text-[color:var(--g-text-muted)]">
          Curated icons + soft identity colors. Status stays separate. Suggested for “{roleHint}”:{" "}
          {ROLE_ICON_REGISTRY[suggested].label}.
        </p>
      </div>

      <div className="flex items-center gap-4">
        <GravitreAgentIdentity
          icon={icon}
          identityColor={color}
          status="available"
          variant="picker"
          size="lg"
        />
        <div>
          <p className="text-sm font-medium">{ROLE_ICON_REGISTRY[icon].label}</p>
          <p className="text-xs text-[color:var(--g-text-muted)]">
            {IDENTITY_COLOR_TOKENS[color].label} · {ROLE_ICON_REGISTRY[icon].source}
          </p>
        </div>
      </div>

      <div>
        <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
          Icon
        </p>
        <div className="grid grid-cols-4 gap-2 sm:grid-cols-7">
          {ICON_IDS.map((id) => {
            const { Icon, label } = ROLE_ICON_REGISTRY[id]
            const active = icon === id
            return (
              <button
                key={id}
                type="button"
                title={label}
                onClick={() => setIcon(id)}
                className={cn(
                  "flex h-11 flex-col items-center justify-center rounded-md border text-[9px]",
                  active
                    ? "border-[color:var(--g-brand)] bg-[color:var(--g-brand-soft)]/40"
                    : "border-divide hover:border-[color:var(--g-brand-border)]",
                )}
              >
                <Icon className="h-4 w-4 text-[color:var(--g-text-primary)]" />
              </button>
            )
          })}
        </div>
      </div>

      <div>
        <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
          Color
        </p>
        <div className="flex flex-wrap gap-2">
          {COLOR_IDS.map((id) => {
            const tok = IDENTITY_COLOR_TOKENS[id]
            const active = color === id
            return (
              <button
                key={id}
                type="button"
                title={tok.label}
                onClick={() => setColor(id)}
                className={cn(
                  "h-8 w-8 rounded-md border",
                  tok.surfaceClass,
                  tok.borderClass,
                  active && "ring-2 ring-[color:var(--g-brand)]/55",
                )}
              />
            )
          })}
        </div>
      </div>
    </div>
  )
}
