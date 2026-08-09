"use client"

import { Suspense, useEffect, useMemo, useState } from "react"
import { useSearchParams } from "next/navigation"
import { useAuth } from "@/lib/auth-context"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { PRODUCTION_BACKEND_URL, publicAppUrl } from "@/lib/public-urls"
import { Button } from "@/components/ui/button"

/**
 * Auth bridge for the Chrome extension.
 * Opens from the extension; sends Supabase access token + org id via
 * chrome.runtime.sendMessage (externally_connectable).
 */
function ExtensionConnectInner() {
  const params = useSearchParams()
  const extId = params.get("ext_id") || ""
  const { session, loading } = useAuth()
  const [orgId, setOrgId] = useState<string>("")
  const [status, setStatus] = useState<string>("")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setOrgId(getSelectedOrgFromStorage()?.id || "")
  }, [session])

  const ready = useMemo(
    () => Boolean(extId && session?.access_token && orgId),
    [extId, session?.access_token, orgId],
  )

  useEffect(() => {
    if (loading) setStatus("Checking your Gravitre session…")
    else if (!session) setStatus("Sign in to Gravitre, then return here to connect the extension.")
    else if (!orgId) setStatus("Select an organization in the app, then connect the extension.")
    else if (!extId) setStatus("Open this page from the Gravitre Chrome extension.")
    else setStatus("Ready to authorize the extension with your current session.")
  }, [loading, session, orgId, extId])

  const connect = async () => {
    if (!ready || !session?.access_token || !orgId) return
    setBusy(true)
    setStatus("Sending session to the extension…")
    try {
      const chromeApi = (
        window as unknown as {
          chrome?: { runtime?: { sendMessage?: (id: string, msg: unknown, cb: (r: unknown) => void) => void } }
        }
      ).chrome
      if (!chromeApi?.runtime?.sendMessage) {
        setStatus("Open this page from Chrome with the extension installed.")
        setBusy(false)
        return
      }
      chromeApi.runtime.sendMessage(
        extId,
        {
          type: "GRAVITRE_AUTH",
          accessToken: session.access_token,
          orgId,
          environment: "production",
          apiBase: PRODUCTION_BACKEND_URL,
          appBase: publicAppUrl(),
        },
        (response: unknown) => {
          setBusy(false)
          const typed = response as { ok?: boolean; error?: string } | undefined
          if (typed?.ok) {
            setStatus("Connected. You can close this tab and use the extension.")
          } else {
            setStatus(typed?.error || "Extension did not accept the session.")
          }
        },
      )
    } catch (err) {
      setBusy(false)
      setStatus(err instanceof Error ? err.message : "Connect failed")
    }
  }

  return (
    <div className="mx-auto flex min-h-[60vh] max-w-lg flex-col justify-center gap-4 p-6">
      <h1 className="text-2xl font-semibold tracking-tight">Connect Gravitre extension</h1>
      <p className="text-sm text-muted-foreground">
        The extension uses your existing Gravitre login and organization — no separate
        identity. Overlay actions go through the same write-authority gate and Outcomes as
        chat.
      </p>
      <p className="text-sm">{status}</p>
      <div className="flex gap-2">
        <Button disabled={!ready || busy} onClick={connect}>
          {busy ? "Connecting…" : "Authorize extension"}
        </Button>
        {!session ? (
          <Button variant="outline" asChild>
            <a href="/login">Sign in</a>
          </Button>
        ) : null}
      </div>
    </div>
  )
}

export default function ExtensionConnectPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
      <ExtensionConnectInner />
    </Suspense>
  )
}
