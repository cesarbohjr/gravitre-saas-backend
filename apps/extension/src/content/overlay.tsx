import { useCallback, useEffect, useRef, useState } from "react"
import { ArrowUpRight, Sparkles, X } from "lucide-react"

import { BrandLoader } from "@/components/brand-loader"
import { BrandMark } from "@/components/brand-mark"
import { Button, Divider, SectionLabel } from "@/components/ui"
import { cn } from "@/lib/cn"
import * as api from "@/lib/messaging"
import { SURFACE_LABELS, surfaceForUrl } from "@/lib/messaging"
import type {
  EnrichResult,
  ExtensionWorkflow,
  Suggestion,
} from "@/lib/types"
import { ApprovalPanel, OutcomePanel } from "./approval-panel"
import { AskSection } from "./ask-section"
import { ExtractedFields, MatchList } from "./enrichment-view"
import { WorkflowSection } from "./workflow-section"

const APP_BASE = "https://gravitre.app"

function openInApp(path: string | undefined, appBase: string) {
  const p = path || "/ai"
  window.open(`${appBase}${p.startsWith("/") ? p : `/${p}`}`, "_blank", "noopener")
}

type Pending = {
  suggestion: Suggestion
  params: Record<string, unknown>
  token: string
}

type Outcome = {
  action?: string
  message?: string
  url?: string
}

export function Overlay({
  pageUrl,
  pageContext,
  onClose,
}: {
  pageUrl: string
  pageContext: Record<string, unknown>
  onClose: () => void
}) {
  const [result, setResult] = useState<EnrichResult | null>(null)
  const [enrichError, setEnrichError] = useState<string>()
  const [loading, setLoading] = useState(true)

  const [workflows, setWorkflows] = useState<ExtensionWorkflow[]>([])
  const [wfLoading, setWfLoading] = useState(true)
  const [wfError, setWfError] = useState<string>()
  const [wfBusyId, setWfBusyId] = useState<string>()

  const [staging, setStaging] = useState<string>()
  const [pending, setPending] = useState<Pending | null>(null)
  const [approveBusy, setApproveBusy] = useState(false)
  const [approveError, setApproveError] = useState<string>()
  const [outcome, setOutcome] = useState<Outcome | null>(null)
  const [notice, setNotice] = useState<string>()

  const [question, setQuestion] = useState("")
  const [chatBusy, setChatBusy] = useState(false)
  const [answer, setAnswer] = useState<string>()
  const [needsHandoff, setNeedsHandoff] = useState(false)
  const conversationId = useRef<string | null>(null)
  const handoffUrl = useRef<string | undefined>(undefined)
  const appBase = useRef(APP_BASE)

  const surface = SURFACE_LABELS[surfaceForUrl(pageUrl)]

  useEffect(() => {
    let alive = true
    void api.enrich(pageUrl, pageContext).then((res) => {
      if (!alive) return
      setLoading(false)
      if (!res.ok) {
        setEnrichError(res.error || "Could not enrich this page.")
        return
      }
      const r = res.result || {}
      setResult(r)
      if (r.openInGravitreeUrl) handoffUrl.current = r.openInGravitreeUrl
    })

    void api.listWorkflows().then((res) => {
      if (!alive) return
      setWfLoading(false)
      if (!res.ok) {
        setWfError(res.error || "Could not load workflows.")
        return
      }
      setWorkflows(res.result?.workflows || [])
    })

    // The app base is configured per environment; prefer it over the constant
    // so self-hosted and staging orgs get correct hand-off links.
    void api.getSession().then((res) => {
      if (!alive) return
      const base = res.session?.openAppUrl || res.cfg?.appBase
      if (base) appBase.current = base.replace(/\/$/, "")
    })

    return () => {
      alive = false
    }
  }, [pageUrl, pageContext])

  // Escape closes the overlay, but only when no approval is awaiting a decision
  // — losing a staged write to a stray keypress would be worse than a click.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !pending) onClose()
    }
    window.addEventListener("keydown", onKey, true)
    return () => window.removeEventListener("keydown", onKey, true)
  }, [pending, onClose])

  /** Step 1 of the write gate: ask the server to stage and issue a token. */
  const stage = useCallback(
    async (suggestion: Suggestion, overrides?: Record<string, unknown>) => {
      const { buildParamsForAction } = await import("@/lib/params")
      const base =
        suggestion.params && Object.keys(suggestion.params).length
          ? { ...suggestion.params }
          : buildParamsForAction(suggestion.invokeAction, result?.extracted || {}, result || {})
      const params = { ...base, ...(overrides || {}) }

      const res = await api.proposeAction({
        invokeAction: suggestion.invokeAction,
        params,
        pageUrl,
      })
      if (!res.ok) return { error: res.error || "Could not stage this action." }
      if (res.result?.status !== "needs_confirmation") {
        // The server completed without gating (a read-only action).
        return {
          done: res.result?.success
            ? { action: suggestion.invokeAction }
            : undefined,
          error: res.result?.success ? undefined : res.result?.error || "Action did not run.",
        }
      }
      if (!res.result.confirmationToken) {
        return { error: "Server did not issue a confirmation token — write blocked." }
      }
      return {
        pending: {
          suggestion,
          params: res.result.params || params,
          token: res.result.confirmationToken,
        } satisfies Pending,
      }
    },
    [pageUrl, result],
  )

  const onSuggestionClick = useCallback(
    async (suggestion: Suggestion) => {
      setNotice(undefined)
      setOutcome(null)
      setApproveError(undefined)
      setStaging(suggestion.invokeAction)
      const out = await stage(suggestion)
      setStaging(undefined)
      if (out.error) return setNotice(out.error)
      if (out.done) return setOutcome({ action: out.done.action })
      if (out.pending) setPending(out.pending)
    },
    [stage],
  )

  /** Step 2: commit with the server-issued token. */
  const onApprove = useCallback(
    async (extra?: Record<string, unknown>) => {
      if (!pending) return
      setApproveBusy(true)
      setApproveError(undefined)

      let token = pending.token

      // Staged arguments are immutable once a token is issued, so any value the
      // operator supplies at approval time (a HubSpot list id) requires a fresh
      // stage-and-token round trip rather than being smuggled into execute.
      if (extra && Object.keys(extra).length) {
        const restaged = await stage(pending.suggestion, { ...pending.params, ...extra })
        if (restaged.error || !restaged.pending) {
          setApproveBusy(false)
          setApproveError(restaged.error || "Could not re-stage this write.")
          return
        }
        token = restaged.pending.token
      }

      const res = await api.executeAction({ confirmationToken: token, pageUrl })
      setApproveBusy(false)
      if (!res.ok) return setApproveError(res.error || "Action failed.")

      const r = res.result || {}
      if (!r.success) return setApproveError(r.error || "Action did not succeed.")

      setPending(null)
      setOutcome({
        action: r.invokeAction || pending.suggestion.invokeAction,
        url: r.outcomeUrl,
      })
    },
    [pending, pageUrl, stage],
  )

  const onRunWorkflow = useCallback(
    async (wf: ExtensionWorkflow) => {
      setNotice(undefined)
      setOutcome(null)
      setWfBusyId(wf.id)

      const staged = await api.proposeWorkflow({
        workflowId: wf.id,
        pageUrl,
        parameters: {},
      })
      if (!staged.ok || staged.result?.status !== "needs_confirmation") {
        setWfBusyId(undefined)
        return setNotice(staged.error || "Could not stage this workflow.")
      }
      const token = staged.result.confirmationToken
      if (!token) {
        setWfBusyId(undefined)
        return setNotice("Server did not issue a confirmation token — workflow blocked.")
      }

      const exec = await api.executeWorkflow({ confirmationToken: token, pageUrl })
      setWfBusyId(undefined)
      if (!exec.ok) return setNotice(exec.error || "Workflow failed.")

      const r = exec.result || {}
      if (!r.runId) return setNotice(r.error || "Workflow did not start.")
      setOutcome({
        message: `${wf.name} — run ${r.status || "started"}.`,
      })
    },
    [pageUrl],
  )

  const onAsk = useCallback(async () => {
    const message = question.trim()
    if (!message) return
    setChatBusy(true)
    setAnswer(undefined)
    const res = await api.chat({
      message,
      pageUrl,
      pageContext,
      conversationId: conversationId.current,
    })
    setChatBusy(false)
    if (!res.ok) return setAnswer(res.error || "Chat failed.")
    const r = res.result || {}
    conversationId.current = r.conversationId || conversationId.current
    setAnswer(r.answer || "(no answer)")
    setNeedsHandoff(Boolean(r.needsHandoff))
    if (r.openInGravitreeUrl) handoffUrl.current = r.openInGravitreeUrl
  }, [question, pageUrl, pageContext])

  const extracted = result?.extracted || {}
  const matches = result?.matches || []
  const suggestions = result?.suggestions || []
  const hasAnyData = Object.keys(extracted).length > 0 || matches.length > 0

  return (
    <div
      role="dialog"
      aria-label="Gravitre enrichment"
      className={cn(
        // A hard, opaque boundary is the point: this must never read as part of
        // LinkedIn or Gmail. Opaque card fill + border + the app's strongest
        // elevation, at a fixed offset from the viewport corner.
        "fixed right-3 top-3 flex max-h-[calc(100vh-1.5rem)] w-[min(380px,calc(100vw-1.5rem))] flex-col",
        "gvt-animate-in overflow-hidden rounded-xl border border-border bg-card",
        "font-sans text-foreground antialiased gvt-elevation-4",
      )}
    >
      <header className="flex shrink-0 items-center gap-2 border-b border-border px-3 py-2.5">
        <BrandMark className="h-5 w-5 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-semibold leading-tight text-foreground">
            Gravitre
          </p>
          <p className="truncate text-[11px] leading-tight text-muted-foreground">{surface}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close Gravitre"
          className={cn(
            "shrink-0 rounded-md p-1 text-muted-foreground transition",
            "hover:bg-secondary hover:text-foreground",
            "outline-none focus-visible:ring-2 focus-visible:ring-ring",
          )}
        >
          <X aria-hidden="true" className="h-4 w-4" />
        </button>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-3 py-3">
        {loading && (
          <div className="flex flex-col items-center gap-2.5 py-8">
            <BrandLoader size={22} />
            <p className="text-[12px] text-muted-foreground">
              Reading this page and checking your connectors…
            </p>
          </div>
        )}

        {!loading && enrichError && (
          <div className="py-6 text-center">
            <p className="text-[13px] font-medium text-foreground">Could not enrich this page</p>
            <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
              {enrichError}
            </p>
          </div>
        )}

        {!loading && !enrichError && (
          <>
            {result?.voiceNote && (
              <p className="text-[12px] leading-relaxed text-muted-foreground">
                {result.voiceNote}
              </p>
            )}

            {!hasAnyData && (
              <div className="py-6 text-center">
                <p className="text-[13px] font-medium text-foreground">
                  Nothing to enrich here
                </p>
                <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
                  Gravitre could not find a person or company on this page. Try a profile or a
                  company page.
                </p>
              </div>
            )}

            <ExtractedFields extracted={extracted} />
            <MatchList matches={matches} />

            {suggestions.length > 0 && !pending && (
              <div>
                <SectionLabel>Suggested writes</SectionLabel>
                <div className="mt-1.5 flex flex-col gap-1.5">
                  {suggestions.map((s) => (
                    <Button
                      key={s.invokeAction}
                      variant="secondary"
                      size="sm"
                      loading={staging === s.invokeAction}
                      onClick={() => void onSuggestionClick(s)}
                      className="justify-start"
                    >
                      <Sparkles aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
                      <span className="min-w-0 flex-1 truncate text-left">{s.label}</span>
                    </Button>
                  ))}
                </div>
                <p className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground">
                  You will see the exact data before anything is written.
                </p>
              </div>
            )}

            {pending && (
              <ApprovalPanel
                suggestion={pending.suggestion}
                params={pending.params}
                busy={approveBusy}
                error={approveError}
                onApprove={(extra) => void onApprove(extra)}
                onCancel={() => {
                  setPending(null)
                  setApproveError(undefined)
                }}
              />
            )}

            {outcome && (
              <OutcomePanel
                action={outcome.action}
                message={outcome.message}
                onOpenOutcome={() =>
                  openInApp(outcome.url || "/outcomes", appBase.current)
                }
                onDismiss={() => setOutcome(null)}
              />
            )}

            {notice && (
              <p role="alert" className="text-[12px] leading-relaxed text-destructive">
                {notice}
              </p>
            )}

            <WorkflowSection
              workflows={workflows}
              loading={wfLoading}
              error={wfError}
              busyId={wfBusyId}
              onRun={(wf) => void onRunWorkflow(wf)}
            />

            <Divider />

            <AskSection
              value={question}
              onChange={setQuestion}
              onAsk={() => void onAsk()}
              onHandoff={() => openInApp(handoffUrl.current, appBase.current)}
              busy={chatBusy}
              answer={answer}
              needsHandoff={needsHandoff}
              canHandoff={Boolean(answer)}
            />
          </>
        )}
      </div>

      <footer className="flex shrink-0 items-center justify-between border-t border-border px-3 py-2">
        <button
          type="button"
          onClick={() => openInApp(handoffUrl.current, appBase.current)}
          className={cn(
            "inline-flex items-center gap-1 rounded-md text-[11px] text-muted-foreground transition",
            "hover:text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring",
          )}
        >
          Open Gravitre
          <ArrowUpRight aria-hidden="true" className="h-3 w-3" />
        </button>
        <span className="text-[11px] text-muted-foreground">Writes need approval</span>
      </footer>
    </div>
  )
}
