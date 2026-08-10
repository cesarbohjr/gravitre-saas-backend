"use client"

import { Suspense, useEffect, useMemo, useState } from "react"
import { useAuth } from "@/lib/auth-context"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { PRODUCTION_BACKEND_URL, publicAppUrl } from "@/lib/public-urls"
import { Button } from "@/components/ui/button"

/**
 * Auth bridge for the Tauri desktop companion.
 * Mirrors /extension/connect: reuse the existing Supabase session, then hand
 * the token to the desktop app via gravitre://auth deep link (no second login).
 */
function DesktopConnectInner() {
  const { session, loading } = useAuth()
  const [orgId, setOrgId] = useState("")
  const [status, setStatus] = useState("")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setOrgId(getSelectedOrgFromStorage()?.id || "")
  }, [session])

  const ready = useMemo(
    () => Boolean(session?.access_token && orgId),
    [session?.access_token, orgId],
  )

  useEffect(() => {
    if (loading) setStatus("Checking your Gravitre session…")
    else if (!session) setStatus("Sign in to Gravitre, then return here to connect Desktop.")
    else if (!orgId) setStatus("Select an organization in the app, then connect Desktop.")
    else setStatus("Ready to authorize the Gravitre desktop companion with this session.")
  }, [loading, session, orgId])

  const connect = () => {
    if (!ready || !session?.access_token || !orgId) return
    setBusy(true)
    setStatus("Opening the desktop app…")
    const params = new URLSearchParams({
      access_token: session.access_token,
      org_id: orgId,
      environment: "production",
      api_base: PRODUCTION_BACKEND_URL,
      app_base: publicAppUrl(),
    })
    const deepLink = `gravitre://auth?${params.toString()}`
    window.location.href = deepLink
    setTimeout(() => {
      setBusy(false)
      setStatus(
        "If the desktop app did not open, ensure Gravitre Desktop is installed, then try again.",
      )
    }, 1200)
  }

  return (
    <div className="mx-auto flex min-h-[60vh] max-w-lg flex-col justify-center gap-4 p-6">
      <h1 className="text-2xl font-semibold tracking-tight">Connect Gravitre Desktop</h1>
      <p className="text-sm text-muted-foreground">
        Uses your existing gravitre.app login and organization — same identity as web and the
        Chrome extension. Chat, activity, and approvals stay in the companion; Settings, Meson,
        Agents, and Billing open in the browser.
      </p>
      <p className="text-sm">{status}</p>
      <div className="flex gap-2">
        <Button disabled={!ready || busy} onClick={connect}>
          {busy ? "Connecting…" : "Authorize Desktop"}
        </Button>
        {!session ? (
          <Button variant="outline" asChild>
            <a href="/login?next=/desktop/connect">Sign in</a>
          </Button>
        ) : null}
      </div>
    </div>
  )
}

export default function DesktopConnectPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
      <DesktopConnectInner />
    </Suspense>
  )
}
