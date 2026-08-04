import { useCallback, useEffect, useState } from "react"
import { ArrowUpRight, RefreshCw, Sparkles } from "lucide-react"

import { BrandLoader, BrandMark } from "@/components/brand-loader"
import { ConnectorChip, SurfaceIcon } from "@/components/connector-icon"
import { ScopePanel } from "@/components/scope-panel"
import { Badge, Button, Card, Divider, Notice, SectionLabel } from "@/components/ui"
import {
  SURFACE_LABELS,
  getSession,
  injectCompanyOverlay,
  openConnect,
  surfaceForUrl,
  usageSignal,
} from "@/lib/messaging"
import type { Session, Surface } from "@/lib/types"

type State =
  | { phase: "loading" }
  | { phase: "disconnected"; error?: string }
  | { phase: "connected"; session: Session }

/**
 * The side panel's real advantage over the popup is that it persists while the
 * user moves between tabs, so it tracks the active surface live instead of
 * snapshotting it once. Everything else is the same verified capability — no
 * invented panels.
 */
export function SidePanelApp() {
  const [state, setState] = useState<State>({ phase: "loading" })
  const [tab, setTab] = useState<{ id?: number; url: string } | null>(null)

  const readTab = useCallback(async () => {
    const [active] = await chrome.tabs.query({ active: true, currentWindow: true })
    setTab({ id: active?.id, url: active?.url ?? "" })
  }, [])

  const load = useCallback(async () => {
    setState({ phase: "loading" })
    const res = await getSession()
    await readTab()
    if (!res.ok) {
      setState({ phase: "disconnected", error: res.error })
      return
    }
    if (!res.signedIn || !res.session) {
      setState({ phase: "disconnected" })
      return
    }
    setState({ phase: "connected", session: res.session })
  }, [readTab])

  useEffect(() => {
    void load()
  }, [load])

  // Live surface tracking — the reason to use the panel over the popup.
  useEffect(() => {
    const onActivated = () => void readTab()
    const onUpdated = (
      _id: number,
      change: { url?: string },
      t: chrome.tabs.Tab,
    ) => {
      if (t.active && change.url) void readTab()
    }
    chrome.tabs.onActivated.addListener(onActivated)
    chrome.tabs.onUpdated.addListener(onUpdated)
    return () => {
      chrome.tabs.onActivated.removeListener(onActivated)
      chrome.tabs.onUpdated.removeListener(onUpdated)
    }
  }, [readTab])

  const url = tab?.url ?? ""
  const surface: Surface = surfaceForUrl(url)
  const supported = surface !== "unknown"

  return (
    <div className="gvt-scope flex min-h-dvh flex-col bg-background text-foreground">
      <header className="flex items-center gap-2 border-b border-border px-4 py-3">
        <span className="inline-flex h-6 w-6 items-center justify-center rounded-md bg-primary/12 text-primary">
          <BrandMark size={14} />
        </span>
        <span className="flex-1 text-[13px] font-semibold tracking-tight">Gravitre</span>
        {state.phase === "connected" && (
          <Badge tone="success">
            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-success" />
            Connected
          </Badge>
        )}
        <button
          type="button"
          onClick={load}
          aria-label="Refresh connection status"
          className="inline-flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground outline-none transition-colors hover:bg-secondary hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
        >
          <RefreshCw aria-hidden="true" className="h-3.5 w-3.5" />
        </button>
      </header>

      {state.phase === "loading" && (
        <div className="flex flex-1 flex-col items-center justify-center gap-3">
          <BrandLoader size={52} className="text-foreground" />
          <p className="text-[12px] text-muted-foreground">Checking your connection…</p>
        </div>
      )}

      {state.phase === "disconnected" && (
        <div className="flex flex-col gap-3 p-4">
          <div>
            <h1 className="text-[15px] font-semibold leading-snug tracking-tight text-balance">
              Enrich the page, approve the write
            </h1>
            <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
              Connect once to read context from your own connectors and approve CRM
              writes without leaving the tab.
            </p>
          </div>
          <Button block onClick={() => void openConnect()}>
            Connect Gravitre
          </Button>
          {state.error && <Notice tone="danger">{state.error}</Notice>}
          <ScopePanel />
        </div>
      )}

      {state.phase === "connected" && (
        <div className="flex flex-1 flex-col gap-4 p-4">
          {/* Current surface — updates as tabs change. */}
          <Card className="p-3">
            <SectionLabel>Current tab</SectionLabel>
            <div className="mt-2 flex items-center gap-2">
              <SurfaceIcon surface={surface} />
              <span className="min-w-0 flex-1 truncate text-[12px] font-medium">
                {supported ? SURFACE_LABELS[surface] : "Unsupported surface"}
              </span>
            </div>
            <p className="mt-1.5 truncate font-mono text-[10px] text-muted-foreground">
              {url || "—"}
            </p>
            <Button
              block
              className="mt-3"
              disabled={!tab?.id}
              onClick={() => {
                if (!tab?.id) return
                void usageSignal({
                  pageUrl: url,
                  invoked: true,
                  note: supported
                    ? "sidepanel_enrich_allowlisted"
                    : "sidepanel_enrich_outside",
                })
                if (supported) {
                  chrome.tabs.sendMessage(tab.id, { type: "OPEN_OVERLAY" })
                } else {
                  void injectCompanyOverlay()
                }
              }}
            >
              <Sparkles aria-hidden="true" className="h-3.5 w-3.5" />
              {supported ? "Enrich this page" : "Try on this page"}
            </Button>
            {!supported && (
              <Notice className="mt-2">
                No reader for this site yet. Gravitre will try generic company
                details and record that you wanted it here.
              </Notice>
            )}
          </Card>

          <div>
            <SectionLabel>Workspace</SectionLabel>
            <dl className="mt-2 flex items-baseline gap-2">
              <dt className="sr-only">Organisation</dt>
              <dd className="min-w-0 flex-1 truncate font-mono text-[11px] text-muted-foreground">
                {state.session.orgId}
              </dd>
              {state.session.role && (
                <>
                  <dt className="sr-only">Role</dt>
                  <dd>
                    <Badge tone="neutral" className="capitalize">
                      {state.session.role}
                    </Badge>
                  </dd>
                </>
              )}
            </dl>
          </div>

          <div>
            <SectionLabel>
              {(state.session.connectedIntegrations?.length ?? 0) > 0
                ? `Active connectors · ${state.session.connectedIntegrations!.length}`
                : "Connectors"}
            </SectionLabel>
            {(state.session.connectedIntegrations?.length ?? 0) > 0 ? (
              <ul className="mt-2 flex flex-wrap gap-1">
                {state.session.connectedIntegrations!.map((name) => (
                  <li key={name}>
                    <ConnectorChip name={name} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-[12px] leading-relaxed text-muted-foreground">
                No connectors yet — connect Apollo or HubSpot in Gravitre to enrich
                pages.
              </p>
            )}
          </div>

          <Divider />

          <ScopePanel allowedActionCount={state.session.allowedActions?.length} />

          <span className="flex-1" />

          <a
            href={state.session.openAppUrl || "https://gravitre.app"}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 rounded text-[11px] text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
          >
            Open Gravitre
            <ArrowUpRight aria-hidden="true" className="h-3 w-3" />
          </a>
        </div>
      )}
    </div>
  )
}
