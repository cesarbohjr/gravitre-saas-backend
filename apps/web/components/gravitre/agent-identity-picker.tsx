"use client"

import { cn } from "@/lib/utils"
import {
  suggestAgentColor,
  suggestAgentIcon,
  type AgentAvatarColorId,
  type AgentIconId,
} from "@/lib/agent-identity"
import { departmentIdFor } from "@/lib/department-icons"
import { ROSTER_DEPARTMENTS } from "@/lib/agents-roster"
import { AgentIdentityAvatar } from "@/components/gravitre/agent-identity-avatar"

interface AgentIdentityPickerProps {
  name: string
  icon: AgentIconId
  avatarColor: AgentAvatarColorId
  /** The agent's department; its icon is the agent's mark everywhere. */
  department?: string | null
  /** Kept for callers that still pass them; the icon now follows the department. */
  onIconChange?: (icon: AgentIconId) => void
  onColorChange?: (color: AgentAvatarColorId) => void
  className?: string
}

/** Appearance preview: every agent wears its department's icon and colour. */
export function AgentIdentityPicker({ name, icon, avatarColor, department, className }: AgentIdentityPickerProps) {
  const deptLabel = departmentLabelFor(department)
  return (
    <div className={cn("flex items-center gap-4", className)}>
      <AgentIdentityAvatar agent={{ name, icon, avatarColor, department }} size="lg" showStatusDot={false} />
      <div>
        <p className="text-sm font-medium text-foreground">Agent appearance</p>
        <p className="text-xs text-muted-foreground">
          Agents wear their department&apos;s icon, so this one shows the {deptLabel} icon. Change the department to change it.
        </p>
      </div>
    </div>
  )
}

function departmentLabelFor(department: string | null | undefined): string {
  const id = departmentIdFor(department)
  return ROSTER_DEPARTMENTS.find((d) => d.id === id)?.name ?? "General"
}

export function useSuggestedAgentIdentity(
  name: string,
  purpose?: string,
  department?: string,
) {
  const icon = suggestAgentIcon(name, purpose, null, department)
  const avatarColor = suggestAgentColor(icon, name, department)
  return { icon, avatarColor }
}
