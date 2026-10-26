"use client"

import { Suspense, useCallback, useEffect, useRef, useState, type ReactNode } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { ArrowLeftRight, Check, CircleAlert, PanelRight, Search, X } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { getSelectedOrgFromStorage, setSelectedOrgInStorage, type SelectedOrg } from "@/lib/org-context"
import { PRODUCTION_BACKEND_URL, publicAppUrl } from "@/lib/public-urls"
import { createCompanionSession } from "@/lib/companion-session"
import { extensionInstallHref } from "@/lib/extension-install"
import { GravitreMark } from "@/components/brand/gravitre-mark"
import { cn } from "@/lib/utils"

/**
 * Auth bridge for the browser extension.
 * Opens from the extension; mints a separate session for it and sends that
 * session + org id via chrome.runtime.sendMessage (externally_connectable).
 */

/** The published Chrome Web Store build, for when the page is opened without ?ext_id. */
const STORE_EXTENSION_ID = "mdjhabfjkieockbppehakknkoeoalonj"

type Phase = "checking" | "ready" | "authorizing" | "connected" | "missing" | "error"

type Runtime = {
  sendMessage?: (id: string, msg: unknown, cb: (r: unknown) => void) => void
  lastError?: { message?: string }
}

function runtime(): Runtime | null {
  return (window as unknown as { chrome?: { runtime?: Runtime } }).chrome?.runtime ?? null
}

type Reply = { ok?: boolean; error?: string; transportError?: string }

function message(extId: string, body: Record<string, unknown>, timeoutMs = 4000): Promise<Reply> {
  const rt = runtime()
  if (!rt?.sendMessage) return Promise.resolve({ transportError: "not available" })
  return new Promise((resolve) => {
    const timer = window.setTimeout(() => resolve({ transportError: "timed out" }), timeoutMs)
    try {
      rt.sendMessage!(extId, body, (response: unknown) => {
        window.clearTimeout(timer)
        resolve({ ...((response as Reply | undefined) || {}), transportError: rt.lastError?.message })
      })
    } catch (err) {
      window.clearTimeout(timer)
      resolve({ transportError: err instanceof Error ? err.message : "unreachable" })
    }
  })
}

function MarkTile({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex size-7 items-center justify-center rounded-[8px] bg-[color:var(--g-carbon)]", className)}>
      <GravitreMark className="h-[10px] text-white" title="" aria-hidden />
    </span>
  )
}

function Badge({ tone, children }: { tone: "ok" | "quiet" | "danger"; children: ReactNode }) {
  const tones = {
    ok: "bg-[color:var(--g-brand-soft)] text-[color:var(--brand-text)]",
    quiet: "bg-[color:var(--g-surface-3)] text-[color:var(--g-text-secondary)]",
    danger: "bg-[color:color-mix(in_oklab,var(--g-danger)_14%,transparent)] text-[color:var(--g-danger)]",
  }
  return <span className={cn("inline-flex size-10 items-center justify-center rounded-full", tones[tone])}>{children}</span>
}

const primary =
  "inline-flex h-10 w-full items-center justify-center gap-1.5 rounded-[10px] bg-[color:var(--brand)] px-4 text-sm font-medium text-[color:var(--brand-foreground)] transition-colors hover:bg-[color:var(--g-brand-hover)] disabled:opacity-60"
const secondary =
  "inline-flex h-10 w-full items-center justify-center gap-1.5 rounded-[10px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] px-4 text-sm font-medium text-[color:var(--g-text-primary)] hover:border-[color:var(--g-border-strong)]"
const quiet =
  "inline-flex h-10 w-full items-center justify-center gap-1.5 rounded-[10px] px-4 text-sm font-medium text-[color:var(--g-text-primary)] hover:bg-[color:var(--g-surface-2)]"

function ExtensionConnectInner() {
  const params = useSearchParams()
  const router = useRouter()
  const extId = params.get("ext_id") || STORE_EXTENSION_ID
  const { session, user, loading } = useAuth()
  const [org, setOrg] = useState<SelectedOrg | null>(null)
  const [orgs, setOrgs] = useState<SelectedOrg[]>([])
  const [switching, setSwitching] = useState(false)
  const [phase, setPhase] = useState<Phase>("checking")
  const [detail, setDetail] = useState("")
  const attempt = useRef(0)

  useEffect(() => {
    setOrg(getSelectedOrgFromStorage())
  }, [session])

  // Without a web session, sign in first and come straight back here.
  useEffect(() => {
    if (loading || session) return
    const back = `/extension/connect${params.toString() ? `?${params.toString()}` : ""}`
    router.replace(`/login?redirect=${encodeURIComponent(back)}`)
  }, [loading, session, params, router])

  const detect = useCallback(async () => {
    setPhase("checking")
    const res = await message(extId, { type: "PING" }, 2500)
    setPhase(res.ok ? "ready" : "missing")
  }, [extId])

  useEffect(() => {
    if (session) void detect()
  }, [session, detect])

  const loadOrgs = async () => {
    setSwitching((x) => !x)
    if (orgs.length) return
    try {
      const { organizationsApi } = await import("@/lib/api")
      const { organizations } = await organizationsApi.list()
      setOrgs((organizations ?? []).filter((o) => o.id && o.name).map((o) => ({ id: o.id, name: String(o.name) })))
    } catch {
      setOrgs([])
    }
  }

  const authorize = async () => {
    if (!session?.access_token || !org) return
    const mine = ++attempt.current
    setPhase("authorizing")
    try {
      const companion = await createCompanionSession(session.access_token, "extension")
      const payload = {
        accessToken: companion.accessToken,
        refreshToken: companion.refreshToken,
        expiresAt: companion.expiresAt,
        orgId: org.id,
        environment: "production",
        apiBase: PRODUCTION_BACKEND_URL,
        appBase: publicAppUrl(),
      }
      let result = await message(extId, { type: "GRAVITRE_AUTH", ...payload })
      // Store builds packaged before the brand rename only accept the legacy type.
      if (!result.ok && !result.transportError) result = await message(extId, { type: "GRAVITREE_AUTH", ...payload })
      if (mine !== attempt.current) return
      if (result.ok) setPhase("connected")
      else {
        setDetail(result.transportError ? "" : result.error || "")
        setPhase("error")
      }
    } catch (err) {
      if (mine !== attempt.current) return
      setDetail(err instanceof Error ? err.message : "")
      setPhase("error")
    }
  }

  const cancel = () => {
    attempt.current++
    if (phase === "authorizing") setPhase("ready")
    else router.push("/home")
  }

  const closeTab = () => {
    window.close()
    window.setTimeout(() => router.push("/home"), 300)
  }

  const email = user?.email || ""
  let body: ReactNode = null

  if (phase === "checking" || !session) {
    body = (
      <>
        <MarkTile />
        <h1 className="text-xl font-semibold tracking-tight">Connect the Gravitre extension</h1>
        <p className="text-sm text-[color:var(--g-text-muted)]">Looking for the extension in this browser…</p>
      </>
    )
  } else if (phase === "ready") {
    body = (
      <>
        <span className="flex items-center gap-2 text-[color:var(--g-text-muted)]">
          <MarkTile />
          <ArrowLeftRight className="size-4" aria-hidden />
          <span className="inline-flex size-7 items-center justify-center rounded-[8px] bg-[color:var(--g-surface-3)]">
            <PanelRight className="size-4" aria-hidden />
          </span>
        </span>
        <h1 className="text-xl font-semibold tracking-tight">Connect the Gravitre extension</h1>
        <div className="rounded-[10px] border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-2)] px-3 py-2 text-sm">
          <div className="flex items-center gap-2">
            <span className="min-w-0 flex-1 truncate">
              {[email, org?.name].filter(Boolean).join(" · ") || "Choose a workspace"}
            </span>
            <button type="button" className="text-xs font-medium text-[color:var(--g-signal)] hover:underline" aria-expanded={switching} onClick={() => void loadOrgs()}>
              Switch
            </button>
          </div>
          {switching ? (
            <label className="mt-2 block">
              <span className="sr-only">Workspace</span>
              <select
                className="h-8 w-full rounded-[8px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] px-2 text-sm"
                value={org?.id || ""}
                onChange={(e) => {
                  const next = orgs.find((o) => o.id === e.target.value)
                  if (!next) return
                  setSelectedOrgInStorage(next)
                  setOrg(next)
                  setSwitching(false)
                }}
              >
                {orgs.length ? null : <option value="">Loading workspaces…</option>}
                {orgs.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
        </div>
        <ul className="flex flex-col gap-2 text-sm text-[color:var(--g-text-secondary)]">
          <li className="flex gap-2">
            <Check className="mt-0.5 size-4 shrink-0 text-[color:var(--brand)]" aria-hidden />
            Ask, approve and see activity as you
          </li>
          <li className="flex gap-2">
            <Check className="mt-0.5 size-4 shrink-0 text-[color:var(--brand)]" aria-hidden />
            Only what your role allows
          </li>
          <li className="flex gap-2">
            <X className="mt-0.5 size-4 shrink-0 text-[color:var(--g-text-muted)]" aria-hidden />
            Can&apos;t change settings, billing or policies
          </li>
        </ul>
        <div className="mt-auto flex flex-col gap-1.5 pt-4">
          <button type="button" className={primary} disabled={!org} onClick={() => void authorize()}>
            Authorize extension
          </button>
          <button type="button" className={quiet} onClick={cancel}>
            Cancel
          </button>
        </div>
      </>
    )
  } else if (phase === "authorizing") {
    body = (
      <>
        <MarkTile />
        <h1 className="text-xl font-semibold tracking-tight">Connecting to your browser</h1>
        <p className="text-sm text-[color:var(--g-text-muted)]">Keep this tab open. This takes a few seconds.</p>
        <div className="h-1 overflow-hidden rounded-full bg-[color:var(--g-surface-3)]" role="progressbar" aria-label="Connecting">
          <div className="h-full w-3/5 animate-pulse rounded-full bg-[color:var(--g-signal)]" />
        </div>
        <div className="mt-auto flex flex-col gap-1.5 pt-4">
          <button type="button" className={primary} disabled>
            Authorizing…
          </button>
          <button type="button" className={quiet} onClick={cancel}>
            Cancel
          </button>
        </div>
      </>
    )
  } else if (phase === "connected") {
    body = (
      <>
        <Badge tone="ok">
          <Check className="size-5" aria-hidden />
        </Badge>
        <h1 className="text-xl font-semibold tracking-tight">Extension connected</h1>
        <p className="text-sm text-[color:var(--g-text-muted)]">You can close this tab. Gravitre is ready in your browser&apos;s side panel.</p>
        {org ? <div className="rounded-[10px] border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-2)] px-3 py-2 text-sm">Signed in to {org.name}</div> : null}
        <div className="mt-auto pt-4">
          <button type="button" className={secondary} onClick={closeTab}>
            Close tab
          </button>
        </div>
      </>
    )
  } else if (phase === "missing") {
    body = (
      <>
        <Badge tone="quiet">
          <Search className="size-5" aria-hidden />
        </Badge>
        <h1 className="text-xl font-semibold tracking-tight">We can&apos;t find the extension</h1>
        <p className="text-sm text-[color:var(--g-text-muted)]">
          Install Gravitre for your browser, then come back to this tab. It works in Chrome, Edge and Brave.
        </p>
        <div className="mt-auto flex flex-col gap-1.5 pt-4">
          <a className={primary} href={extensionInstallHref()} target="_blank" rel="noopener noreferrer">
            Install extension ↗
          </a>
          <button type="button" className={secondary} onClick={() => void detect()}>
            I&apos;ve installed it
          </button>
        </div>
      </>
    )
  } else {
    body = (
      <>
        <Badge tone="danger">
          <CircleAlert className="size-5" aria-hidden />
        </Badge>
        <h1 className="text-xl font-semibold tracking-tight">Couldn&apos;t connect</h1>
        <p className="text-sm text-[color:var(--g-text-muted)]">
          {detail || "You're signed in, but the extension didn't answer. Trying again usually fixes it."}
        </p>
        <div className="mt-auto flex flex-col gap-1.5 pt-4">
          <button type="button" className={primary} onClick={() => void authorize()}>
            Try again
          </button>
          <a className={quiet} href="/support" target="_blank" rel="noopener noreferrer">
            Get help ↗
          </a>
        </div>
      </>
    )
  }

  return (
    <div className="flex min-h-dvh flex-col bg-[color:var(--g-canvas)] text-[color:var(--g-text-primary)]">
      <header className="flex h-12 items-center gap-2.5 border-b border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] px-5">
        <MarkTile />
        <span className="text-[15px] font-semibold">Gravitre</span>
      </header>
      <main className="flex flex-1 items-start justify-center px-4 py-10 sm:items-center">
        <section
          aria-live="polite"
          className="flex min-h-[400px] w-full max-w-[340px] flex-col gap-4 rounded-[14px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-6 shadow-[var(--np-shadow)]"
        >
          {body}
        </section>
      </main>
    </div>
  )
}

export default function ExtensionConnectPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-[color:var(--g-text-muted)]">Loading…</div>}>
      <ExtensionConnectInner />
    </Suspense>
  )
}
