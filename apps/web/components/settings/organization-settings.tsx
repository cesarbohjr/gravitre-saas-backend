"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import Image from "next/image"
import useSWR from "swr"
import { toast } from "sonner"
import { Loader2 } from "lucide-react"
import { organizationsApi, settingsApi, type WorkspaceDefaults } from "@/lib/api"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { clearSelectedOrgFromStorage, invalidateOrgCache } from "@/lib/org-context"
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { SettingsSaveBar } from "./settings-save-bar"

const MAX_LOGO_BYTES = 2 * 1024 * 1024

/** Accent colours offered in the design; the choice is the white-label primary colour. */
export const ACCENT_SWATCHES: { name: string; hex: string }[] = [
  { name: "Gravitre green", hex: "#2E9E5B" },
  { name: "Ink", hex: "#1D1E1C" },
  { name: "Indigo", hex: "#5B5BD6" },
  { name: "Clay", hex: "#B0573F" },
  { name: "Slate", hex: "#4A6A8E" },
]

export const TIME_ZONES: { id: string; label: string }[] = [
  { id: "America/Vancouver", label: "Pacific Time (Vancouver)" },
  { id: "America/Los_Angeles", label: "Pacific Time (Los Angeles)" },
  { id: "America/Denver", label: "Mountain Time (Denver)" },
  { id: "America/Chicago", label: "Central Time (Chicago)" },
  { id: "America/Toronto", label: "Eastern Time (Toronto)" },
  { id: "America/New_York", label: "Eastern Time (New York)" },
  { id: "America/Sao_Paulo", label: "Brasilia Time (Sao Paulo)" },
  { id: "UTC", label: "UTC" },
  { id: "Europe/London", label: "UK Time (London)" },
  { id: "Europe/Paris", label: "Central European Time (Paris)" },
  { id: "Europe/Berlin", label: "Central European Time (Berlin)" },
  { id: "Asia/Dubai", label: "Gulf Time (Dubai)" },
  { id: "Asia/Kolkata", label: "India Time (Kolkata)" },
  { id: "Asia/Singapore", label: "Singapore Time" },
  { id: "Asia/Tokyo", label: "Japan Time (Tokyo)" },
  { id: "Australia/Sydney", label: "Australian Eastern Time (Sydney)" },
]

function isLogoUrl(value: string) {
  if (!value || (value.startsWith("/") && !value.startsWith("//"))) return true
  if (value.startsWith("data:image/")) return true
  try {
    return ["http:", "https:"].includes(new URL(value).protocol)
  } catch {
    return false
  }
}

interface Draft {
  name: string
  logoUrl: string
  accentColor: string
  timeZone: string
}

/** Settings > Workspace > General (v5): name, logo, accent colour, time zone, delete. */
export function OrganizationSettings({
  orgData,
  onUpdate,
  isAdmin,
}: {
  orgData: Record<string, unknown>
  onUpdate: () => Promise<void>
  isAdmin: boolean
}) {
  const orgId = String(orgData.id ?? "")
  const { data: workspaceData, mutate: mutateWorkspace } = useSWR<{ workspace: WorkspaceDefaults }>(
    "/api/settings/workspace",
    apiFetcher,
    { revalidateOnFocus: false },
  )
  const workspace = workspaceData?.workspace
  // A logo uploaded or removed here is already saved; show it until the refreshed org arrives.
  const serverLogo = String(orgData.logoUrl ?? orgData.logo_url ?? "")
  const [savedLogo, setSavedLogo] = useState<string | null>(null)
  useEffect(() => setSavedLogo(null), [serverLogo])
  const baseline = useMemo<Draft>(
    () => ({
      name: String(orgData.name ?? ""),
      logoUrl: savedLogo ?? serverLogo,
      accentColor: (workspace?.accentColor ?? ACCENT_SWATCHES[0].hex).toUpperCase(),
      timeZone: workspace?.timeZone ?? "UTC",
    }),
    [orgData.name, savedLogo, serverLogo, workspace?.accentColor, workspace?.timeZone],
  )
  const [draft, setDraft] = useState<Draft>(baseline)
  const [touched, setTouched] = useState<Partial<Record<keyof Draft, boolean>>>({})
  // Keep unsaved edits; take fresh server values only for fields not being edited.
  useEffect(() => {
    setDraft((previous) => ({
      name: touched.name ? previous.name : baseline.name,
      logoUrl: touched.logoUrl ? previous.logoUrl : baseline.logoUrl,
      accentColor: touched.accentColor ? previous.accentColor : baseline.accentColor,
      timeZone: touched.timeZone ? previous.timeZone : baseline.timeZone,
    }))
  }, [baseline, touched])

  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState<number | null>(null)
  const [logoBusy, setLogoBusy] = useState<"upload" | "remove" | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleteText, setDeleteText] = useState("")
  const [deleting, setDeleting] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const inFlight = useRef(false)

  const dirty =
    draft.name !== baseline.name ||
    draft.logoUrl !== baseline.logoUrl ||
    draft.accentColor !== baseline.accentColor ||
    draft.timeZone !== baseline.timeZone
  const disabled = !isAdmin || saving || logoBusy !== null
  const logoPreview = isLogoUrl(draft.logoUrl) ? draft.logoUrl : baseline.logoUrl
  const zoneOptions = TIME_ZONES.some((zone) => zone.id === draft.timeZone)
    ? TIME_ZONES
    : [{ id: draft.timeZone, label: draft.timeZone }, ...TIME_ZONES]

  const change = <K extends keyof Draft>(key: K, value: Draft[K]) => {
    setDraft((previous) => ({ ...previous, [key]: value }))
    setTouched((previous) => ({ ...previous, [key]: true }))
    setError(null)
  }

  async function refresh() {
    try {
      await onUpdate()
    } catch {
      toast.error("Settings saved, but the workspace could not be refreshed.")
    }
  }

  async function save() {
    if (!isAdmin || inFlight.current || !dirty) return
    if (!draft.name.trim()) {
      setError("Give the workspace a name.")
      return
    }
    if (!isLogoUrl(draft.logoUrl)) {
      setError("Enter a valid logo image URL or leave it empty.")
      return
    }
    inFlight.current = true
    setSaving(true)
    setError(null)
    try {
      if (draft.name !== baseline.name || draft.logoUrl !== baseline.logoUrl) {
        // The organization endpoint replaces all four fields, so send slug and domain unchanged.
        await settingsApi.updateOrg({
          name: draft.name.trim(),
          slug: String(orgData.slug ?? ""),
          primaryDomain: String(orgData.primaryDomain ?? orgData.primary_domain ?? ""),
          logoUrl: draft.logoUrl,
        })
      }
      if (draft.accentColor !== baseline.accentColor || draft.timeZone !== baseline.timeZone) {
        const result = await settingsApi.updateWorkspace({ accentColor: draft.accentColor, timeZone: draft.timeZone })
        await mutateWorkspace(result, { revalidate: false })
      }
      await refresh()
      setTouched({})
      setSavedAt(Date.now())
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not save the workspace settings")
    } finally {
      inFlight.current = false
      setSaving(false)
    }
  }

  function discard() {
    setDraft(baseline)
    setTouched({})
    setError(null)
  }

  async function uploadLogo(file: File) {
    if (!isAdmin || inFlight.current) return
    if (!file.type.startsWith("image/")) {
      setError("Choose a PNG or SVG image for the logo.")
      return
    }
    if (file.size > MAX_LOGO_BYTES) {
      setError("The logo is over 2MB.")
      return
    }
    inFlight.current = true
    setLogoBusy("upload")
    setError(null)
    try {
      const result = await settingsApi.uploadOrgLogo(file)
      const next = String(result.logoUrl ?? result.organization?.logoUrl ?? result.organization?.logo_url ?? "")
      if (!next) throw new Error("The server accepted the file but did not return a saved logo.")
      setSavedLogo(next)
      setTouched((previous) => ({ ...previous, logoUrl: false }))
      setSavedAt(Date.now())
      await refresh()
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not upload the logo")
    } finally {
      inFlight.current = false
      setLogoBusy(null)
      if (fileInput.current) fileInput.current.value = ""
    }
  }

  async function removeLogo() {
    if (!isAdmin || inFlight.current) return
    inFlight.current = true
    setLogoBusy("remove")
    setError(null)
    try {
      await settingsApi.removeOrgLogo()
      setSavedLogo("")
      setTouched((previous) => ({ ...previous, logoUrl: false }))
      setSavedAt(Date.now())
      await refresh()
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not remove the logo")
    } finally {
      inFlight.current = false
      setLogoBusy(null)
    }
  }

  async function deleteWorkspace() {
    if (!isAdmin || !orgId || deleteText.trim() !== baseline.name.trim()) return
    setDeleting(true)
    try {
      await organizationsApi.delete(orgId)
      clearSelectedOrgFromStorage()
      invalidateOrgCache()
      toast.success("Workspace deleted")
      window.location.assign("/settings/organizations")
    } catch (failure) {
      toast.error(failure instanceof Error ? failure.message : "Could not delete the workspace")
      setDeleting(false)
    }
  }

  return (
    <>
      {!isAdmin ? (
        <p className="st-note">Only owners and admins can change these settings.</p>
      ) : null}
      <section aria-label="Workspace" className="st-card">
        <div className="st-row">
          <div className="st-what">
            <label htmlFor="organization-name">Workspace name</label>
            <span>Shown in the top bar and on shared reports.</span>
          </div>
          <div className="st-control">
            <input
              id="organization-name"
              type="text"
              className="st-input"
              value={draft.name}
              disabled={disabled}
              onChange={(event) => change("name", event.target.value)}
            />
          </div>
        </div>
        <div className="st-row">
          <div className="st-what">
            <b>Logo</b>
            <span>PNG or SVG up to 2MB. Square works best.</span>
          </div>
          <div className="st-control wrap">
            <span className="st-logo">
              {logoPreview ? (
                <Image src={logoPreview} alt="Workspace logo" width={64} height={64} unoptimized />
              ) : (
                <svg width="34" height="22" viewBox="0 0 34 22" aria-label="No logo yet">
                  <path d="M4 4h26l-6 6H4z" fill="#4CC27F" />
                  <path d="M10 12h20l-6 6H4z" fill="#2E9E5B" />
                </svg>
              )}
            </span>
            <div className="st-logo-side">
              <div className="st-logo-actions">
                <input
                  ref={fileInput}
                  id="organization-logo-file"
                  type="file"
                  accept="image/png,image/svg+xml,image/*"
                  className="sr-only"
                  disabled={disabled}
                  onChange={(event) => {
                    const file = event.target.files?.[0]
                    if (file) void uploadLogo(file)
                  }}
                />
                <button type="button" className="st-btn" disabled={disabled} onClick={() => fileInput.current?.click()}>
                  {logoBusy === "upload" ? <Loader2 size={14} className="animate-spin motion-reduce:animate-none" aria-hidden /> : null}
                  {logoBusy === "upload" ? "Uploading..." : "Upload logo"}
                </button>
                {baseline.logoUrl ? (
                  <button type="button" className="st-btn ghost red" disabled={disabled} onClick={() => void removeLogo()}>
                    {logoBusy === "remove" ? "Removing..." : "Remove"}
                  </button>
                ) : null}
              </div>
              <label htmlFor="organization-logoUrl" className="sr-only">
                Logo image URL
              </label>
              <input
                id="organization-logoUrl"
                type="url"
                className="st-input sm"
                placeholder="Or paste an image URL"
                value={draft.logoUrl.startsWith("data:") ? "" : draft.logoUrl}
                aria-invalid={!isLogoUrl(draft.logoUrl)}
                disabled={disabled}
                onChange={(event) => change("logoUrl", event.target.value.trim())}
              />
            </div>
          </div>
        </div>
        <div className="st-row">
          <div className="st-what">
            <b id="accent-label">Accent color</b>
            <span>Used on buttons and highlights in shared reports.</span>
          </div>
          <div className="st-control">
            <div className="st-swatches" role="group" aria-labelledby="accent-label">
              {ACCENT_SWATCHES.map((swatch) => (
                <button
                  key={swatch.hex}
                  type="button"
                  className="st-swatch"
                  aria-label={swatch.name}
                  aria-pressed={draft.accentColor === swatch.hex}
                  disabled={disabled}
                  style={{ background: swatch.hex }}
                  onClick={() => change("accentColor", swatch.hex)}
                />
              ))}
            </div>
          </div>
        </div>
        <div className="st-row">
          <div className="st-what">
            <label htmlFor="organization-timezone">Time zone</label>
            <span>Schedules and SLAs follow this clock.</span>
          </div>
          <div className="st-control">
            <select
              id="organization-timezone"
              className="st-select"
              value={draft.timeZone}
              disabled={disabled}
              onChange={(event) => change("timeZone", event.target.value)}
            >
              {zoneOptions.map((zone) => (
                <option key={zone.id} value={zone.id}>
                  {zone.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>
      {error ? (
        <p role="alert" className="st-error">
          {error}
        </p>
      ) : null}

      {isAdmin ? (
        <section aria-label="Danger zone" className="st-danger">
          <div>
            <b>Delete workspace</b>
            <span>Removes agents, runs and connected sources. This cannot be undone.</span>
          </div>
          <button type="button" className="st-btn danger" onClick={() => setConfirmDelete(true)}>
            Delete workspace
          </button>
        </section>
      ) : null}

      <AlertDialog
        open={confirmDelete}
        onOpenChange={(open) => {
          setConfirmDelete(open)
          if (!open) setDeleteText("")
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {baseline.name || "this workspace"}?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes its agents, runs and connected sources for everyone, and cannot be undone. Type the
              workspace name to confirm.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <label htmlFor="delete-workspace-confirm" className="sr-only">
            Workspace name
          </label>
          <input
            id="delete-workspace-confirm"
            className="flex h-11 w-full rounded-md border border-input bg-background px-3 text-base"
            value={deleteText}
            placeholder={baseline.name}
            onChange={(event) => setDeleteText(event.target.value)}
          />
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
            <button
              type="button"
              className="inline-flex min-h-10 items-center justify-center rounded-md bg-destructive px-4 text-sm font-medium text-destructive-foreground disabled:opacity-50"
              disabled={deleting || deleteText.trim() !== baseline.name.trim()}
              onClick={() => void deleteWorkspace()}
            >
              {deleting ? "Deleting..." : "Delete workspace"}
            </button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <SettingsSaveBar dirty={dirty && isAdmin} saving={saving} savedAt={savedAt} onDiscard={discard} onSave={() => void save()} />
    </>
  )
}
