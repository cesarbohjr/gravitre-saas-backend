"use client"

import { useEffect, useState } from "react"
import { mutate as globalMutate } from "swr"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { AgentIdentityPicker } from "@/components/gravitre/agent-identity-picker"
import {
  coerceAgentColor,
  coerceAgentIcon,
  personalityFromAvatarColor,
  type AgentAvatarColorId,
  type AgentIconId,
} from "@/lib/agent-identity"
import { agentsApi } from "@/lib/api"
import type { Agent } from "@/types/api"
import { LoadingIndicator } from "@/components/gravitre/gravitree-loader"
import { Pencil } from "lucide-react"

interface AgentIdentityEditorProps {
  agent: Agent
}

export function AgentIdentityEditor({ agent }: AgentIdentityEditorProps) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [name, setName] = useState(agent.name)
  const [icon, setIcon] = useState<AgentIconId>(coerceAgentIcon(agent.icon, "bot"))
  const [avatarColor, setAvatarColor] = useState<AgentAvatarColorId>(
    coerceAgentColor(agent.avatarColor, "bg-emerald-500"),
  )

  useEffect(() => {
    if (!open) return
    setName(agent.name)
    setIcon(coerceAgentIcon(agent.icon, "bot"))
    setAvatarColor(coerceAgentColor(agent.avatarColor, "bg-emerald-500"))
  }, [open, agent])

  const handleSave = async () => {
    const trimmedName = name.trim()
    if (!trimmedName) {
      toast.error("Agent name is required")
      return
    }

    setSaving(true)
    try {
      const personality = personalityFromAvatarColor(avatarColor)
      await agentsApi.update(agent.id, {
        name: trimmedName,
        icon,
        avatarColor,
        personality,
      })
      await globalMutate("/api/agents")
      await globalMutate(`agent-profile/${agent.id}`)
      toast.success("Agent identity updated")
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update agent")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <Pencil className="h-3.5 w-3.5" />
          Edit identity
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit agent identity</DialogTitle>
          <DialogDescription>
            Name, icon, and color are shared everywhere this agent appears — list, chat, notifications, and outcomes.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <label htmlFor="agent-identity-name" className="text-sm font-medium text-foreground">
              Name
            </label>
            <Input
              id="agent-identity-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Agent name"
            />
          </div>

          <AgentIdentityPicker
            name={name.trim() || agent.name}
            icon={icon}
            avatarColor={avatarColor}
            onIconChange={setIcon}
            onColorChange={setAvatarColor}
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? (
              <>
                <LoadingIndicator size="xs" className="mr-2" />
                Saving
              </>
            ) : (
              "Save changes"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
