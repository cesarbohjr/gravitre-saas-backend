"use client"

import { useRef, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { Loader2, Save } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { apiFetch, fetcher } from "@/lib/fetcher"

interface NotificationPreferences {
  emailEnabled: boolean
  slackEnabled: boolean
  recipients: string[]
}
interface PreferencesResponse { notifications: NotificationPreferences }
function hasPreferences(value: unknown): value is NotificationPreferences {
  if (!value || typeof value !== "object") return false
  const preferences = value as Partial<NotificationPreferences>
  return typeof preferences.emailEnabled === "boolean" && typeof preferences.slackEnabled === "boolean"
    && Array.isArray(preferences.recipients) && preferences.recipients.every(value => typeof value === "string")
}
const endpoint = "/api/settings/notifications"

export function NotificationSettings({ isAdmin }: { isAdmin: boolean }) {
  const { data, error, isLoading, mutate } = useSWR<PreferencesResponse>(endpoint, fetcher, { revalidateOnFocus: false })
  if (isLoading) return <p role="status" className="py-6 text-sm text-muted-foreground">Loading notification preferences…</p>
  if (error || !hasPreferences(data?.notifications)) return <div role="alert" className="space-y-3 py-4">
    <p className="text-sm">Could not load notification preferences. Try again before making changes.</p>
    <Button variant="outline" className="min-h-11" onClick={() => void mutate()}>Retry preferences</Button>
  </div>
  return <NotificationPreferencesForm preferences={data.notifications} isAdmin={isAdmin}
    onSaved={(notifications) => mutate({ notifications }, { revalidate: false }).then(() => {})} />
}

function NotificationPreferencesForm({ preferences, isAdmin, onSaved }: {
  preferences: NotificationPreferences
  isAdmin: boolean
  onSaved: (preferences: NotificationPreferences) => Promise<void>
}) {
  const [emailEnabled, setEmailEnabled] = useState(preferences.emailEnabled)
  const [slackEnabled, setSlackEnabled] = useState(preferences.slackEnabled)
  const [recipients, setRecipients] = useState(preferences.recipients.join(", "))
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inFlight = useRef(false)
  async function save(event: React.FormEvent) {
    event.preventDefault()
    if (!isAdmin || inFlight.current) return
    const addresses = recipients.split(/[,;\n]/).map(value => value.trim()).filter(Boolean)
    if (addresses.some(value => !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value))) {
      setError("Enter valid email addresses separated by commas."); return
    }
    inFlight.current = true; setSaving(true); setError(null); setSaved(false)
    try {
      const response = await apiFetch(endpoint, { method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ emailEnabled, slackEnabled, recipients: [...new Set(addresses)] }) })
      if (!response.ok) throw new Error("Could not save notification preferences. Try again.")
      const result = await response.json() as PreferencesResponse
      if (!hasPreferences(result.notifications)) throw new Error("The server did not return saved notification preferences.")
      await onSaved(result.notifications)
      setEmailEnabled(result.notifications.emailEnabled); setSlackEnabled(result.notifications.slackEnabled)
      setRecipients(result.notifications.recipients.join(", "))
      setSaved(true); toast.success("Notification preferences saved")
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not save notification preferences")
    } finally { inFlight.current = false; setSaving(false) }
  }
  return <form aria-label="Notification preferences" onSubmit={save} className="space-y-5">
    <p className="text-sm text-muted-foreground">Organization alert channels and recipients. Delivery also depends on a configured email service or Slack connection.</p>
    {!isAdmin && <p className="text-sm text-muted-foreground">Admin or owner permission is required to change these preferences.</p>}
    <fieldset disabled={!isAdmin || saving} className="space-y-4">
      <label className="flex min-h-11 items-center justify-between gap-4 border-b border-divide py-3">
        <span className="min-w-0"><span className="block text-sm font-medium">Email notifications</span>
          <span className="mt-1 block text-sm text-muted-foreground">Receive alerts via email</span></span>
        <input type="checkbox" aria-label="Email notifications" checked={emailEnabled} onChange={(event) => { setEmailEnabled(event.target.checked); setSaved(false) }} className="h-5 w-5 shrink-0 accent-[var(--g-brand-active)]" />
      </label>
      <label className="flex min-h-11 items-center justify-between gap-4 border-b border-divide py-3">
        <span className="min-w-0"><span className="block text-sm font-medium">Slack notifications</span>
          <span className="mt-1 block text-sm text-muted-foreground">Send alerts through your Slack connection</span></span>
        <input type="checkbox" aria-label="Slack notifications" checked={slackEnabled} onChange={(event) => { setSlackEnabled(event.target.checked); setSaved(false) }} className="h-5 w-5 shrink-0 accent-[var(--g-brand-active)]" />
      </label>
      <div className="space-y-2">
        <label htmlFor="notification-recipients" className="text-sm font-medium">Alert recipients</label>
        <Input id="notification-recipients" value={recipients} onChange={(event) => { setRecipients(event.target.value); setSaved(false) }}
          className="min-h-11 bg-card" aria-describedby="notification-recipients-hint" />
        <p id="notification-recipients-hint" className="text-xs text-muted-foreground">Separate email addresses with commas.</p>
      </div>
    </fieldset>
    <Button asChild variant="outline" className="min-h-11"><Link href="/connectors">Manage Slack connection</Link></Button>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    <div className="flex flex-wrap items-center gap-3 border-t border-divide pt-4">
      <Button type="submit" disabled={!isAdmin || saving} className="min-h-11 gap-2">
        {saving ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Save className="h-4 w-4" />}
        {saving ? "Saving…" : "Save changes"}
      </Button>
      {saved && <p role="status" className="text-sm text-[color:var(--g-brand-active)]">Preferences saved</p>}
    </div>
  </form>
}
