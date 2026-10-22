"use client"

import { Suspense, useEffect, useMemo, useState } from "react"
import { useSearchParams } from "next/navigation"
import { useAuth } from "@/lib/auth-context"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { PRODUCTION_BACKEND_URL, publicAppUrl } from "@/lib/public-urls"
import { Button } from "@/components/ui/button"
import { createCompanionSession } from "@/lib/companion-session"

// The desktop app shows the same code while it waits, and only accepts a
// deep link that carries it back.
const CODE_PATTERN = /^[A-Z0-9]{3} ?[A-Z0-9]{3}$/

/**
 * Auth bridge for the Tauri desktop companion.
 * Reuses the web login (no second sign-in), mints a separate session for the
 * desktop app, and hands it over through the gravitre://auth deep link.
 */
function DesktopConnectInner() {
  const params = useSearchParams()
  const rawCode = (params.get("code") || "").toUpperCase()
  const code = CODE_PATTERN.test(rawCode) ? rawCode : ""
  const { session, loading } = useAuth()
  const [orgId, setOrgId] = useState("")
  const [status, setStatus] = useState("")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setOrgId(getSelectedOrgFromStorage()?.id || "")
  }, [session])

  const ready = useMemo(
    () => Boolean(session?.access_token && orgId && code),
    [session?.access_token, orgId, code],
  )

  useEffect(() => {
    if (loading) setStatus("Checking your Gravitre session…")
    else if (!session) setStatus("Sign in to Gravitre, then return here to connect Desktop.")
    else if (!orgId) setStatus("Select an organization in the app, then connect Desktop.")
    else if (!code) setStatus("Open this page from the Gravitre desktop app's sign-in button.")
    else setStatus("Check that the code below matches the one in the desktop app, then authorize.")
  }, [loading, session, orgId, code])

  const connect = async () => {
    if (!ready || !session?.access_token || !orgId) return
    setBusy(true)
    setStatus("Creating a session for the desktop app…")
    try {
      const companion = await createCompanionSession(session.access_token, "desktop")
      const link = new URLSearchParams({
        access_token: companion.accessToken,
        refresh_token: companion.refreshToken,
        expires_at: String(companion.expiresAt ?? ""),
        org_id: orgId,
        code: code.replace(" ", ""),
        environment: "production",
        api_base: PRODUCTION_BACKEND_URL,
        app_base: publicAppUrl(),
      })
      setStatus("Opening the desktop app…")
      window.location.href = `gravitre://auth?${link.toString()}`
      setTimeout(() => {
        setBusy(false)
        setStatus(
          "If the desktop app did not open, make sure Gravitre Desktop is installed and still waiting, then try again.",
        )
      }, 1500)
    } catch (err) {
      setBusy(false)
      setStatus(err instanceof Error ? err.message : "Could not connect the desktop app.")
    }
  }

  return (
    <div className="mx-auto flex min-h-[60vh] max-w-lg flex-col justify-center gap-4 p-6">
      <h1 className="text-2xl font-semibold tracking-tight">Connect Gravitre Desktop</h1>
      <p className="text-sm text-muted-foreground">
        Uses your existing gravitre.app login and organization — same identity as web and the
        Chrome extension. Chat, activity, and approvals stay in the companion; Settings, Meson,
        Agents, and Billing open in the browser.
      </p>
      {code ? (
        <div className="rounded-lg border border-divide p-4 text-center">
          <p className="text-xs text-muted-foreground">Sign-in code</p>
          <p className="mt-1 font-mono text-2xl font-semibold tracking-[0.2em]">
            {code.replace(/^(.{3}) ?(.{3})$/, "$1 $2")}
          </p>
        </div>
      ) : null}
      <p className="text-sm">{status}</p>
      <div className="flex gap-2">
        <Button disabled={!ready || busy} onClick={connect}>
          {busy ? "Connecting…" : "Authorize Desktop"}
        </Button>
        {!session ? (
          <Button variant="outline" asChild>
            <a href={`/login?next=${encodeURIComponent(`/desktop/connect${code ? `?code=${code.replace(" ", "")}` : ""}`)}`}>Sign in</a>
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
