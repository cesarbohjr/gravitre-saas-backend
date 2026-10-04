"use client"

import { useRef, useState } from "react"
import Image from "next/image"
import { Building2, Loader2, Save } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { settingsApi } from "@/lib/api"

function isLogoUrl(value: string) {
  if (!value || (value.startsWith("/") && !value.startsWith("//"))) return true
  try { return ["http:", "https:"].includes(new URL(value).protocol) } catch { return false }
}

export function OrganizationSettings({ orgData, onUpdate, isAdmin }: {
  orgData: Record<string, unknown>
  onUpdate: () => Promise<void>
  isAdmin: boolean
}) {
  const [draft, setDraft] = useState(() => ({
    name: String(orgData.name ?? ""), slug: String(orgData.slug ?? ""),
    primaryDomain: String(orgData.primaryDomain ?? orgData.primary_domain ?? ""),
    logoUrl: String(orgData.logoUrl ?? orgData.logo_url ?? ""),
  }))
  const [logoPreview, setLogoPreview] = useState(draft.logoUrl)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inFlight = useRef(false)
  const change = (key: keyof typeof draft, value: string) => {
    setDraft((previous) => ({ ...previous, [key]: value })); setSaved(false)
  }
  async function save(event: React.FormEvent) {
    event.preventDefault()
    if (!isAdmin || inFlight.current) return
    if (!isLogoUrl(draft.logoUrl)) { setError("Enter a valid logo image URL or leave it empty."); return }
    inFlight.current = true; setSaving(true); setError(null)
    try {
      // Include the current logo: the existing organization endpoint replaces all four fields.
      await settingsApi.updateOrg(draft)
      setLogoPreview(draft.logoUrl); setSaved(true); toast.success("Organization settings saved")
      try { await onUpdate() } catch { toast.error("Settings saved, but the organization could not be refreshed.") }
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not save organization settings")
    } finally { inFlight.current = false; setSaving(false) }
  }
  return <form onSubmit={save} className="space-y-6" aria-label="Organization settings">
    <div className="flex flex-wrap items-center gap-4 border-b border-divide pb-5">
      <div className="flex h-16 w-32 shrink-0 items-center justify-center rounded-lg border border-divide bg-card p-2">
        {logoPreview && isLogoUrl(logoPreview) ? <Image src={logoPreview} alt="Organization logo" width={112} height={48} unoptimized className="max-h-12 w-auto object-contain" />
          : <Building2 className="h-8 w-8 text-muted-foreground" aria-label="No organization logo" />}
      </div>
      <div className="min-w-0"><h2 className="text-sm font-medium">Organization identity</h2>
        <p className="mt-1 text-sm text-muted-foreground">Update your workspace name, domain, and logo.</p></div>
    </div>
    {!isAdmin && <p className="text-sm text-muted-foreground">Admin or owner permission is required to change organization settings.</p>}
    <fieldset disabled={!isAdmin || saving} className="grid min-w-0 gap-5 sm:grid-cols-2">
      {([
        ["name", "Organization name", "text"], ["slug", "Organization slug", "text"],
        ["primaryDomain", "Primary domain", "text"], ["logoUrl", "Logo URL", "text"],
      ] as const).map(([key, label, type]) => <div key={key} className="min-w-0 space-y-2">
        <label htmlFor={`organization-${key}`} className="text-sm font-medium">{label}</label>
        <Input id={`organization-${key}`} type={type} value={draft[key]} onChange={(event) => change(key, event.target.value)}
          className="min-h-11 bg-card" aria-describedby={key === "logoUrl" ? "organization-logo-hint" : undefined} />
        {key === "logoUrl" && <p id="organization-logo-hint" className="text-xs text-muted-foreground">Use the URL of an existing logo image. File upload is not available here.</p>}
      </div>)}
    </fieldset>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    <div className="flex flex-wrap items-center gap-3 border-t border-divide pt-4">
      <Button type="submit" disabled={!isAdmin || saving} className="min-h-11 gap-2">
        {saving ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Save className="h-4 w-4" />}
        {saving ? "Saving…" : "Save changes"}
      </Button>
      {saved && <p role="status" className="text-sm text-[color:var(--g-brand-active)]">Changes saved</p>}
    </div>
  </form>
}
