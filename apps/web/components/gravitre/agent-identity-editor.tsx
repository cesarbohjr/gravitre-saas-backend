"use client"

import { useRef, useState } from "react"
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
import { AGENT_DEPARTMENT_OPTIONS } from "@/lib/agent-display"
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
  const [department, setDepartment] = useState(agent.department || "General")
  const [icon, setIcon] = useState<AgentIconId>(
    coerceAgentIcon(agent.icon, "bot"),
  )
  const [avatarColor, setAvatarColor] = useState<AgentAvatarColorId>(
    coerceAgentColor(agent.avatarColor, "bg-emerald-500"),
  )
  const [avatarUrl, setAvatarUrl] = useState<string | null>(
    agent.avatarUrl ?? null,
  )
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [error, setError] = useState<string | null>(null)
  const busyRef = useRef(false)
  const busy = saving || uploading
  function changeOpen(next: boolean) {
    if (busyRef.current) return
    if (next) {
      setName(agent.name)
      setDepartment(agent.department || "General")
      setIcon(coerceAgentIcon(agent.icon, "bot"))
      setAvatarColor(coerceAgentColor(agent.avatarColor, "bg-emerald-500"))
      setAvatarUrl(agent.avatarUrl ?? null)
      setError(null)
    }
    setOpen(next)
  }

  const refreshCaches = async () => {
    await Promise.allSettled([
      globalMutate("/api/agents"),
      globalMutate(`agent-profile/${agent.id}`),
      globalMutate(`agent/${agent.id}`),
    ])
  }

  const handleUpload = async (file: File) => {
    if (!file.type.startsWith("image/") || file.size > 5 * 1024 * 1024) {
      setError("Choose an image no larger than 5MB")
      return
    }
    if (busyRef.current) return
    busyRef.current = true
    setError(null)
    setUploading(true)
    try {
      const payload = await agentsApi.uploadAvatar(agent.id, file)
      setAvatarUrl(payload.avatarUrl ?? null)
      await refreshCaches()
      toast.success("Agent photo updated")
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Failed to upload avatar",
      )
    } finally {
      setUploading(false)
      busyRef.current = false
    }
  }

  const handleRemoveImage = async () => {
    if (busyRef.current) return
    busyRef.current = true
    setError(null)
    setUploading(true)
    try {
      await agentsApi.removeAvatar(agent.id)
      setAvatarUrl(null)
      await refreshCaches()
      toast.success("Agent photo removed")
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Failed to remove avatar",
      )
    } finally {
      setUploading(false)
      busyRef.current = false
    }
  }

  const handleSave = async () => {
    if (busyRef.current) return
    const trimmedName = name.trim()
    if (!trimmedName) {
      setError("Agent name is required")
      return
    }

    busyRef.current = true
    setError(null)
    setSaving(true)
    try {
      const personality = personalityFromAvatarColor(avatarColor)
      await agentsApi.update(agent.id, {
        name: trimmedName,
        department,
        icon,
        avatarColor,
        personality,
      })
      await refreshCaches()
      toast.success("Agent identity updated")
      setOpen(false)
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Failed to update agent",
      )
    } finally {
      setSaving(false)
      busyRef.current = false
    }
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="min-h-11 gap-2">
          <Pencil className="h-3.5 w-3.5" />
          Edit identity
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-sans">
            Edit agent identity
          </DialogTitle>
          <DialogDescription>
            Name, department and optional photo are shared
            everywhere this agent appears.
          </DialogDescription>
        </DialogHeader>

        <fieldset disabled={busy} className="min-w-0 space-y-4 py-2">
          <div className="space-y-2">
            <label
              htmlFor="agent-identity-name"
              className="text-sm font-medium text-foreground"
            >
              Name
            </label>
            <Input
              className="min-h-11"
              id="agent-identity-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Agent name"
            />
          </div>

          <div className="space-y-2">
            <label
              htmlFor="agent-identity-department"
              className="text-sm font-medium text-foreground"
            >
              Department
            </label>
            <select
              id="agent-identity-department"
              value={department}
              onChange={(event) =>
                setDepartment(
                  event.target.value as NonNullable<Agent["department"]>,
                )
              }
              className="min-h-11 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            >
              {!AGENT_DEPARTMENT_OPTIONS.some((dept) => dept === department) ? (
                <option value={department}>{department}</option>
              ) : null}
              {AGENT_DEPARTMENT_OPTIONS.map((dept) => (
                <option key={dept} value={dept}>
                  {dept}
                </option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground">
              Controls which TEAM lane this agent belongs to on the Agents
              roster.
            </p>
          </div>

          <div className="rounded-xl border border-border p-4">
            <div className="mb-3 flex items-center gap-3">
              <AgentIdentityAvatar
                agent={{ name, icon, avatarColor, avatarUrl, department }}
                size="lg"
              />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground">
                  Custom photo
                </p>
                <p className="text-xs text-muted-foreground">
                  Photos save immediately, including if you cancel the other
                  edits. Max 5MB.
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
                className="min-h-11 gap-2"
                disabled={busy}
                onClick={() => fileInputRef.current?.click()}
              >
                {uploading ? (
                  <LoadingIndicator size="xs" />
                ) : (
                  <ImagePlus className="h-3.5 w-3.5" />
                )}
                {avatarUrl ? "Replace photo" : "Upload photo"}
              </Button>
              {avatarUrl ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="min-h-11 gap-2 text-destructive"
                  disabled={busy}
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
              department={department}
              name={name.trim() || agent.name}
              icon={icon}
              avatarColor={avatarColor}
              onIconChange={setIcon}
              onColorChange={setAvatarColor}
            />
          ) : (
            <p className="text-xs text-muted-foreground">
              The photo replaces the department icon while it is set. Remove
              the photo to show the department icon again.
            </p>
          )}
        </fieldset>
        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
        <DialogFooter>
          <Button
            variant="outline"
            className="min-h-11"
            onClick={() => changeOpen(false)}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button
            className="min-h-11"
            onClick={handleSave}
            disabled={busy || !name.trim()}
          >
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
