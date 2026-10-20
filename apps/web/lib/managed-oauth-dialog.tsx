"use client"

import { useState } from "react"
import { createRoot } from "react-dom/client"
import { Dialog, DialogContent, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { connectorsApi } from "./api"

export type OAuthInputField = { key: string; label: string; required: boolean; enum?: string[]; pattern?: string; example?: string }
type Session = Awaited<ReturnType<typeof connectorsApi.startManagedAuth>>
type Props = {
  name: string
  fields: OAuthInputField[]
  initialSession?: Session
  prepare: (params: Record<string, string>) => Promise<Session>
  authorize: (session: Session) => Promise<void>
}

export function ManagedOAuthDialog({ name, fields, initialSession, prepare, authorize, finish }: Props & { finish: (connected: boolean) => void }) {
  const [params, setParams] = useState<Record<string, string>>({})
  const [session, setSession] = useState(initialSession)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (busy) return
    setError("")
    setBusy(true)
    if (!session) {
      void prepare(params).then(setSession).catch(() => setError("Sign-in could not be prepared. Check the account details and try again."))
        .finally(() => setBusy(false))
      return
    }
    // Keep this call in the click event; awaiting preparation here would block popups in Safari.
    try {
      await authorize(session)
      finish(true)
    } catch (cause: unknown) {
      const type = cause && typeof cause === "object" && "type" in cause ? cause.type : ""
      if (type === "window_closed" || type === "authorization_cancelled") {
        finish(false)
        return
      }
      setError(type === "blocked_by_browser"
        ? "Allow popups for Gravitre, then try again."
        : "We couldn’t confirm the connection. Close this window and reconnect to try again.")
      // Tokens may be single-use or expired. Prepare a fresh attempt on retry.
      setSession(undefined)
      setBusy(false)
    }
  }
  return <Dialog open onOpenChange={(open) => { if (!open && !busy) finish(false) }}>
    <DialogContent showCloseButton={!busy} onEscapeKeyDown={(event) => { if (busy) event.preventDefault() }} onPointerDownOutside={(event) => event.preventDefault()}>
      <DialogTitle>Connect {name}</DialogTitle>
      <DialogDescription>Sign in with your provider to authorize Gravitre. Choose the account and review its requested permissions before approving access.</DialogDescription>
      <form onSubmit={submit} className="space-y-4">
        {!session && fields.map((field) => <div key={field.key} className="space-y-1">
          <label htmlFor={`oauth-${field.key}`} className="text-sm">{field.label}{field.required ? "" : " (optional)"}</label>
          {field.enum ? <select id={`oauth-${field.key}`} required={field.required} value={params[field.key] ?? ""}
            onChange={(event) => setParams({ ...params, [field.key]: event.target.value })} className="w-full rounded-md border bg-background p-2 text-sm">
            <option value="">Select {field.label.toLowerCase()}</option>
            {field.enum.map((value) => <option key={value} value={value}>{value}</option>)}
          </select> : <Input id={`oauth-${field.key}`} required={field.required} maxLength={253} pattern={field.pattern}
            placeholder={field.example} value={params[field.key] ?? ""} disabled={busy}
            onChange={(event) => setParams({ ...params, [field.key]: event.target.value })} />}
        </div>)}
        {busy && <p role="status" className="text-sm text-muted-foreground">{session ? "Complete sign-in in the provider window. Confirming your connection…" : "Preparing secure sign-in…"}</p>}
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <DialogFooter>
          <Button type="button" variant="outline" disabled={busy} onClick={() => finish(false)}>Cancel</Button>
          <Button type="submit" disabled={busy}>{session ? "Sign in with provider" : "Continue"}</Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
}

export function showManagedOAuthDialog(props: Props): Promise<boolean> {
  const container = document.createElement("div")
  document.body.append(container)
  const root = createRoot(container)
  return new Promise((resolve) => {
    let settled = false
    root.render(<ManagedOAuthDialog {...props} finish={(connected) => {
      if (settled) return
      settled = true
      resolve(connected)
      // Unmount outside the active React event/render stack.
      setTimeout(() => { root.unmount(); container.remove() }, 0)
    }} />)
  })
}
