"use client"

import { useRef, useState } from "react"
import { mutate as globalMutate } from "swr"
import { toast } from "@/components/agents/overlays/toast"
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
import { AGENT_DEPARTMENT_OPTIONS } from "@/lib/agent-display"
import { agentsApi } from "@/lib/api"
import { identityDepartmentFor } from "@/lib/listing-identity"
import type { Agent } from "@/types/api"
import { LoadingIndicator } from "@/components/gravitre/gravitre-loader"
import { DepartmentCover, ListingBadge } from "@/components/marketplace/identity/listing-identity"
import { ImagePlus, Pencil, Trash2 } from "lucide-react"

interface AgentIdentityEditorProps {
  agent: Agent
  /** "button" is the labelled outline button; "icon" is the pencil beside the agent's name. */
  trigger?: "button" | "icon"
}

/** Live preview: the agent's cover, avatar, name and lane, as they will show everywhere. */
function IdentityPreview({ name, department, avatarUrl }: { name: string; department: string; avatarUrl: string | null }) {
  const dept = identityDepartmentFor(department)
  return (
    <div className="overflow-hidden rounded-xl border border-[#e4e4df] dark:border-[#2a2c29]">
      <DepartmentCover department={department} kindLabel="Live preview" className="h-[120px] [&_.li-banner-tags]:left-auto [&_.li-banner-tags]:right-3 [&_.li-banner-tags]:top-3 [&_.li-tag.dark]:hidden" />
      <div className="relative flex items-center gap-3 px-4 pb-3 pt-2">
        <span className="-mt-9 shrink-0">
          {avatarUrl ? (
            // eslint-disable-next-line @next/next/no-img-element -- agent avatars may be data URLs
            <img src={avatarUrl} alt="" className="size-14 rounded-full border-2 border-white object-cover shadow-md" />
          ) : (
            <ListingBadge kind="agent" department={dept} size={56} />
          )}
        </span>
        <span className="min-w-0">
          <span className="block truncate text-base font-semibold">{name || "Unnamed agent"}</span>
          <span className="text-[13px] font-medium" style={{ color: dept.color }}>
            Agent · {dept.label}
          </span>
        </span>
      </div>
    </div>
  )
}

export function AgentIdentityEditor({ agent, trigger = "button" }: AgentIdentityEditorProps) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [name, setName] = useState(agent.name)
  const [department, setDepartment] = useState(agent.department || "General")
  const [description, setDescription] = useState(agent.description ?? "")
  const [avatarUrl, setAvatarUrl] = useState<string | null>(agent.avatarUrl ?? null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [error, setError] = useState<string | null>(null)
  const busyRef = useRef(false)
  const busy = saving || uploading
  function changeOpen(next: boolean) {
    if (busyRef.current) return
    if (next) {
      setName(agent.name)
      setDepartment(agent.department || "General")
      setDescription(agent.description ?? "")
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
      setError("Choose an image no larger than 5 MB")
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
      toast.success("Photo updated", { eyebrow: "Agents", description: `${agent.name} shows the new photo everywhere.` })
    } catch (error) {
      setError(error instanceof Error ? error.message : "Failed to upload avatar")
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
      toast.success("Photo removed", { eyebrow: "Agents", description: "The department icon shows again." })
    } catch (error) {
      setError(error instanceof Error ? error.message : "Failed to remove avatar")
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
      await agentsApi.update(agent.id, {
        name: trimmedName,
        department,
        description: description.trim(),
      })
      await refreshCaches()
      toast.success("Identity updated", { eyebrow: "Agents", description: `${trimmedName} is shown with the new identity everywhere.` })
      setOpen(false)
    } catch (error) {
      setError(error instanceof Error ? error.message : "Failed to update agent")
    } finally {
      setSaving(false)
      busyRef.current = false
    }
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>
        {trigger === "icon" ? (
          <button
            type="button"
            aria-label="Edit identity"
            className="grid size-9 shrink-0 place-items-center rounded-lg bg-[#efefea] text-[#33342f] transition-colors hover:bg-[#e4e4df] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#19c37d] dark:bg-[#262825] dark:text-[#d6d6d0] max-sm:size-11"
          >
            <Pencil className="size-3.5" aria-hidden />
          </button>
        ) : (
          <Button variant="outline" size="sm" className="min-h-11 gap-2">
            <Pencil className="h-3.5 w-3.5" />
            Edit identity
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-[460px]">
        <DialogHeader>
          <DialogTitle>Edit identity</DialogTitle>
          <DialogDescription>Shown everywhere this agent appears.</DialogDescription>
        </DialogHeader>

        <IdentityPreview name={name.trim()} department={department} avatarUrl={avatarUrl} />

        <fieldset disabled={busy} className="min-w-0 space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="agent-identity-name" className="text-sm font-medium">
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

          <div className="space-y-1.5">
            <label htmlFor="agent-identity-department" className="text-sm font-medium">
              Department
            </label>
            <select
              id="agent-identity-department"
              value={department}
              onChange={(event) => setDepartment(event.target.value as NonNullable<Agent["department"]>)}
              className="min-h-11 w-full rounded-[10px] border border-[#e4e4df] bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#19c37d]/40 dark:border-[#2a2c29] dark:bg-[#171917]"
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
            <p className="text-xs text-[#55564f] dark:text-[#a3a49c]">Sets the team lane, scene, color and icon.</p>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="agent-identity-description" className="text-sm font-medium">
              Description
            </label>
            <textarea
              id="agent-identity-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              placeholder="What this agent does, in a sentence or two"
              className="w-full resize-y rounded-[10px] border border-[#e4e4df] bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#19c37d]/40 dark:border-[#2a2c29] dark:bg-[#171917]"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
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
            <button
              type="button"
              className="ag-btn sm ghost"
              disabled={busy}
              onClick={() => fileInputRef.current?.click()}
            >
              {uploading ? <LoadingIndicator size="xs" /> : <ImagePlus className="size-4" aria-hidden />}
              {avatarUrl ? "Replace photo" : "Upload photo"}
            </button>
            {avatarUrl ? (
              <button type="button" className="ag-btn sm ghost text-[#a3333d]" disabled={busy} onClick={() => void handleRemoveImage()}>
                <Trash2 className="size-4" aria-hidden />
                Remove
              </button>
            ) : null}
            <span className="text-xs text-[#8a8b85]">Optional. Max 5 MB. Photos save right away.</span>
          </div>
        </fieldset>
        {error ? (
          <p role="alert" className="text-sm text-[#a3333d]">
            {error}
          </p>
        ) : null}
        <DialogFooter>
          <Button variant="outline" className="min-h-11" onClick={() => changeOpen(false)} disabled={busy}>
            Cancel
          </Button>
          <Button className="min-h-11" onClick={handleSave} disabled={busy || !name.trim()}>
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
