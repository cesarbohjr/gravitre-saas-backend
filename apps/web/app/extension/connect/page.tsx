"use client"

import { Suspense, useEffect, useMemo, useState } from "react"
import { useSearchParams } from "next/navigation"
import { useAuth } from "@/lib/auth-context"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { PRODUCTION_BACKEND_URL, publicAppUrl } from "@/lib/public-urls"
import { Button } from "@/components/ui/button"
import { createCompanionSession } from "@/lib/companion-session"

/**
 * Auth bridge for the Chrome extension.
 * Opens from the extension; mints a separate session for it and sends that
 * session + org id via chrome.runtime.sendMessage (externally_connectable).
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
          chrome?: {
            runtime?: {
              sendMessage?: (id: string, msg: unknown, cb: (r: unknown) => void) => void
              lastError?: { message?: string }
            }
          }
        }
      ).chrome
      const runtime = chromeApi?.runtime
      if (!runtime?.sendMessage) {
        setStatus("Open this page from Chrome with the extension installed.")
        setBusy(false)
        return
      }
      const companion = await createCompanionSession(session.access_token, "extension")
      const payload = {
        accessToken: companion.accessToken,
        refreshToken: companion.refreshToken,
        expiresAt: companion.expiresAt,
        orgId,
        environment: "production",
        apiBase: PRODUCTION_BACKEND_URL,
        appBase: publicAppUrl(),
      }
      type AuthResult = { ok?: boolean; error?: string; transportError?: string }
      const send = (type: string) =>
        new Promise<AuthResult>((resolve) => {
          runtime.sendMessage!(extId, { type, ...payload }, (response: unknown) => {
            const transportError = runtime.lastError?.message
            resolve({ ...((response as AuthResult | undefined) || {}), transportError })
          })
        })
      let result = await send("GRAVITRE_AUTH")
      // Store builds packaged before the brand rename only accept the legacy type.
      if (!result.ok && !result.transportError) result = await send("GRAVITREE_AUTH")
      setBusy(false)
      if (result.ok) {
        setStatus("Connected. You can close this tab and use the extension.")
      } else if (result.transportError) {
        setStatus(
          `Could not reach the extension (${result.transportError}). Update or reinstall it, then reopen this page from the extension.`,
        )
      } else {
        setStatus(result.error || "Extension did not accept the session.")
      }
    } catch (err) {
      setBusy(false)
      setStatus(err instanceof Error ? err.message : "Connect failed")
    }
  }

  return (
    <div className="mx-auto flex min-h-[60vh] max-w-lg flex-col justify-center gap-4 p-[var(--np-page-pad)] sm:p-6">
      <div className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-5 shadow-[var(--np-shadow)] sm:p-6">
        <p className="mb-2 font-mono text-xs font-semibold text-[color:var(--g-text-muted)]">
          Extension
        </p>
        <h1 className="text-xl font-semibold tracking-tight text-[color:var(--g-text-primary)] sm:text-2xl">
          Connect Gravitre extension
        </h1>
        <p className="mt-2 text-sm text-[color:var(--g-text-muted)]">
          The extension uses your existing Gravitre login and organization — no separate
          identity. Overlay actions go through the same write-authority gate and Outcomes as
          chat.
        </p>
        <p className="mt-4 text-sm text-[color:var(--g-text-primary)]">{status}</p>
        <div className="mt-4 flex flex-wrap gap-2">
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
    </div>
  )
}

export default function ExtensionConnectPage() {
  return (
    <Suspense
      fallback={
        <div className="p-6 text-sm text-[color:var(--g-text-muted)]">Loading…</div>
      }
    >
      <ExtensionConnectInner />
    </Suspense>
  )
}
