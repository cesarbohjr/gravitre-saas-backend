import { useCallback, useEffect, useState } from "react"
import { ArrowUpRight, PanelRight, Sparkles } from "lucide-react"

import { BrandLoader, BrandMark } from "@/components/brand-loader"
import { ConnectorChip, SurfaceIcon } from "@/components/connector-icon"
import { ScopePanel } from "@/components/scope-panel"
import { Badge, Button, Divider, Notice, SectionLabel } from "@/components/ui"
import {
  SURFACE_LABELS,
  getSession,
  injectCompanyOverlay,
  openConnect,
  signOut,
  surfaceForUrl,
  usageSignal,
} from "@/lib/messaging"
import type { Session, Surface } from "@/lib/types"

type State =
  | { phase: "loading" }
  | { phase: "disconnected"; error?: string }
  | { phase: "connected"; session: Session }

export function PopupApp() {
  const [state, setState] = useState<State>({ phase: "loading" })
  const [tab, setTab] = useState<{ id?: number; url: string } | null>(null)

  const load = useCallback(async () => {
    setState({ phase: "loading" })
    const [res, tabs] = await Promise.all([
      getSession(),
      chrome.tabs.query({ active: true, currentWindow: true }),
    ])
    const active = tabs?.[0]
    setTab({ id: active?.id, url: active?.url ?? "" })

    if (!res.ok) {
      setState({ phase: "disconnected", error: res.error })
      return
    }
    if (!res.signedIn || !res.session) {
      setState({ phase: "disconnected" })
      return
    }
    setState({ phase: "connected", session: res.session })
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  if (state.phase === "loading") {
    return (
      <Shell>
        <div className="flex flex-col items-center justify-center gap-3 py-12">
          <BrandLoader size={44} className="text-foreground" />
          <p className="text-[12px] text-muted-foreground">Checking your connection…</p>
        </div>
      </Shell>
    )
  }

  if (state.phase === "disconnected") {
    return <Disconnected error={state.error} onRetry={load} />
  }

  return (
    <Connected
      session={state.session}
      tab={tab}
      onSignOut={async () => {
        await signOut()
        void load()
      }}
    />
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="gvt-scope flex w-[360px] flex-col bg-background text-foreground">
      {children}
    </div>
  )
}

function Header({ right }: { right?: React.ReactNode }) {
  return (
    <header className="flex items-center gap-2 px-4 pt-4">
      <span className="inline-flex h-6 w-6 items-center justify-center rounded-md bg-primary/12 text-primary">
        <BrandMark size={14} />
      </span>
      <span className="flex-1 text-[13px] font-semibold tracking-tight text-foreground">
        Gravitre
      </span>
      {right}
    </header>
  )
}

/**
 * One clear action, no clutter (Part A.1). The scope disclosure is shown here
 * too — before connecting is exactly when a user is deciding whether to trust
 * this thing.
 */
function Disconnected({ error, onRetry }: { error?: string; onRetry: () => void }) {
  const [busy, setBusy] = useState(false)

  return (
    <Shell>
      <Header />
      <div className="flex flex-col gap-3 p-4">
        <div>
          <h1 className="text-[15px] font-semibold leading-snug tracking-tight text-balance text-foreground">
            Enrich the page, approve the write
          </h1>
          <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
            Connect once to read context from your own connectors and approve CRM
            writes without leaving the tab.
          </p>
        </div>

        <Button
          block
          disabled={busy}
          onClick={async () => {
            setBusy(true)
            await openConnect()
            setBusy(false)
          }}
        >
          Connect Gravitre
        </Button>

        {error && <Notice tone="danger">{error}</Notice>}
        {error && (
          <Button variant="ghost" size="sm" onClick={onRetry}>
            Try again
          </Button>
        )}

        <ScopePanel />

        <p className="text-[11px] leading-relaxed text-muted-foreground">
          Opens gravitre.app to sign in with your existing org session.
        </p>
      </div>
    </Shell>
  )
}

function Connected({
  session,
  tab,
  onSignOut,
}: {
  session: Session
  tab: { id?: number; url: string } | null
  onSignOut: () => void
}) {
  const url = tab?.url ?? ""
  const surface: Surface = surfaceForUrl(url)
  const supported = surface !== "unknown"
  const connectors = session.connectedIntegrations ?? []

  const enrich = useCallback(() => {
    if (!tab?.id) return
    void usageSignal({
      pageUrl: url,
      invoked: true,
      note: supported
        ? "popup_enrich_allowlisted"
        : "popup_enrich_active_tab_or_outside",
    })
    if (supported) {
      chrome.tabs.sendMessage(tab.id, { type: "OPEN_OVERLAY" })
    } else {
      void injectCompanyOverlay()
    }
    window.close()
  }, [tab?.id, url, supported])

  return (
    <Shell>
      <Header
        right={
          <Badge tone="success">
            <span
              aria-hidden="true"
              className="h-1.5 w-1.5 rounded-full bg-success"
            />
            Connected
          </Badge>
        }
      />

      {/* Part A.2 — glanceable, never ambiguous about whether it's working. */}
      <div className="px-4 pt-3">
        <dl className="flex items-baseline gap-2">
          <dt className="sr-only">Organisation</dt>
          <dd className="min-w-0 flex-1 truncate font-mono text-[11px] text-muted-foreground">
            {session.orgId}
          </dd>
          {session.role && (
            <>
              <dt className="sr-only">Role</dt>
              <dd>
                <Badge tone="neutral" className="capitalize">
                  {session.role}
                </Badge>
              </dd>
            </>
          )}
        </dl>
      </div>

      <div className="px-4 pt-3">
        <SectionLabel>
          {connectors.length > 0
            ? `Active connectors · ${connectors.length}`
            : "Connectors"}
        </SectionLabel>
        {connectors.length > 0 ? (
          <ul className="mt-1.5 flex flex-wrap gap-1">
            {connectors.map((name) => (
              <li key={name}>
                <ConnectorChip name={name} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1.5 text-[12px] leading-relaxed text-muted-foreground">
            No connectors yet — connect Apollo or HubSpot in Gravitre to enrich
            pages.
          </p>
        )}
      </div>

      <Divider className="mx-4 my-3.5" />

      <div className="flex flex-col gap-2 px-4">
        <div className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
          <SurfaceIcon surface={surface} />
          <span className="min-w-0 flex-1 truncate">
            {supported ? SURFACE_LABELS[surface] : "Not a supported surface"}
          </span>
        </div>

        <Button block onClick={enrich} disabled={!tab?.id}>
          <Sparkles aria-hidden="true" className="h-3.5 w-3.5" />
          {supported ? `Enrich this ${SURFACE_LABELS[surface]} page` : "Try on this page"}
        </Button>

        {!supported && (
          <Notice>
            Gravitre has no reader for this site yet. It will try generic company
            details and record that you wanted it here.
          </Notice>
        )}
      </div>

      <div className="flex flex-col gap-2 p-4">
        <Button
          variant="secondary"
          block
          onClick={async () => {
            const [active] = await chrome.tabs.query({
              active: true,
              currentWindow: true,
            })
            if (active?.windowId != null && chrome.sidePanel?.open) {
              await chrome.sidePanel.open({ windowId: active.windowId })
              window.close()
            }
          }}
        >
          <PanelRight aria-hidden="true" className="h-3.5 w-3.5" />
          Open side panel
        </Button>

        <ScopePanel allowedActionCount={session.allowedActions?.length} />

        <div className="flex items-center gap-2 pt-0.5">
          <a
            href={session.openAppUrl || "https://gravitre.app"}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 rounded text-[11px] text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
          >
            Open Gravitre
            <ArrowUpRight aria-hidden="true" className="h-3 w-3" />
          </a>
          <span className="flex-1" />
          <button
            type="button"
            onClick={onSignOut}
            className="rounded text-[11px] text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
          >
            Sign out
          </button>
        </div>
      </div>
    </Shell>
  )
}
