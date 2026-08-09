"use client"

import { useEffect, useRef, useState } from "react"
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
import { LoadingIndicator } from "@/components/gravitre/gravitre-loader"
import { ImagePlus, Pencil, Trash2 } from "lucide-react"
import { AgentIdentityAvatar } from "@/components/gravitre/agent-identity-avatar"

interface AgentIdentityEditorProps {
  agent: Agent
}

export function AgentIdentityEditor({ agent }: AgentIdentityEditorProps) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [name, setName] = useState(agent.name)
  const [icon, setIcon] = useState<AgentIconId>(coerceAgentIcon(agent.icon, "bot"))
  const [avatarColor, setAvatarColor] = useState<AgentAvatarColorId>(
    coerceAgentColor(agent.avatarColor, "bg-emerald-500"),
  )
  const [avatarUrl, setAvatarUrl] = useState<string | null>(agent.avatarUrl ?? null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) return
    setName(agent.name)
    setIcon(coerceAgentIcon(agent.icon, "bot"))
    setAvatarColor(coerceAgentColor(agent.avatarColor, "bg-emerald-500"))
    setAvatarUrl(agent.avatarUrl ?? null)
  }, [open, agent])

  const refreshCaches = async () => {
    await globalMutate("/api/agents")
    await globalMutate(`agent-profile/${agent.id}`)
    await globalMutate(`agent/${agent.id}`)
  }

  const handleUpload = async (file: File) => {
    setUploading(true)
    try {
      const payload = await agentsApi.uploadAvatar(agent.id, file)
      setAvatarUrl(payload.avatarUrl ?? null)
      await refreshCaches()
      toast.success("Agent photo updated")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to upload avatar")
    } finally {
      setUploading(false)
    }
  }

  const handleRemoveImage = async () => {
    setUploading(true)
    try {
      await agentsApi.removeAvatar(agent.id)
      setAvatarUrl(null)
      await refreshCaches()
      toast.success("Agent photo removed")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to remove avatar")
    } finally {
      setUploading(false)
    }
  }

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
      await refreshCaches()
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
            Name, icon, color, and optional photo are shared everywhere this agent appears.
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

          <div className="rounded-xl border border-border p-4">
            <div className="mb-3 flex items-center gap-3">
              <AgentIdentityAvatar
                agent={{ name, icon, avatarColor, avatarUrl }}
                size="lg"
              />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground">Custom photo</p>
                <p className="text-xs text-muted-foreground">
                  Optional. Overrides icon+color when set. Max 5MB.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0]
                  if (file) void handleUpload(file)
                  event.target.value = ""
                }}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="gap-2"
                disabled={uploading}
                onClick={() => fileInputRef.current?.click()}
              >
                {uploading ? <LoadingIndicator size="xs" /> : <ImagePlus className="h-3.5 w-3.5" />}
                {avatarUrl ? "Replace photo" : "Upload photo"}
              </Button>
              {avatarUrl ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="gap-2 text-destructive"
                  disabled={uploading}
                  onClick={() => void handleRemoveImage()}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Remove
                </Button>
              ) : null}
            </div>
          </div>

          {!avatarUrl ? (
            <AgentIdentityPicker
              name={name.trim() || agent.name}
              icon={icon}
              avatarColor={avatarColor}
              onIconChange={setIcon}
              onColorChange={setAvatarColor}
            />
          ) : (
            <p className="text-xs text-muted-foreground">
              Icon and color pickers are hidden while a custom photo is active. Remove the photo to edit them.
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving || uploading}>
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
