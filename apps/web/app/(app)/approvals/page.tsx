"use client"

import { Fragment, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import useSWR, { useSWRConfig } from "swr"
import { useRouter, useSearchParams } from "next/navigation"
import { toast } from "@/components/agents/overlays/toast"
import { AlertTriangle, Check, Lock, MoreHorizontal, RefreshCw, Search, ShieldCheck } from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { WsPage } from "@/components/workspace/ws-page"
import { WsArt } from "@/components/workspace/ws-art"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { useMyCapability } from "@/lib/use-my-capability"
import { approvalsApi } from "@/lib/api"
import { resolveProvider } from "@/lib/provider-registry"
import { cn } from "@/lib/utils"
import { Textarea } from "@/components/ui/textarea"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  decidedByLine,
  environmentLabel,
  formatDate,
  isExtensionGate,
  isPastSla,
  lockNote,
  activity,
  matchesQuery,
  normalizeApprovals,
  parseTime,
  policyCopy,
  policyLine,
  riskLabel,
  slaLine,
  summarySentence,
  titleCase,
  typeLabel,
  whatWillHappen,
  type Approval,
  type QueueTab,
  type RiskLevel,
} from "@/components/approvals/decision-queue/model"
import "@/components/workspace/ops-v4.css"
import "@/components/approvals/decision-queue/decision-queue.css"

const POLICIES_HREF = "/trust-safety?tab=policies"

const RISK_TONE: Record<RiskLevel, string> = { low: "brand", medium: "amber", high: "red" }

function updatedLabel(at: number | null, now: number): string {
  if (at == null) return "Not updated yet"
  const secs = Math.max(0, Math.floor((now - at) / 1000))
  if (secs < 45) return "Updated just now"
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `Updated ${Math.max(1, mins)} min ago`
  return `Updated ${Math.floor(mins / 60)} h ago`
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true
  const tag = target.tagName
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT"
}

function appName(slug: string | null): string {
  if (!slug) return "Gravitre"
  return resolveProvider(slug)?.name ?? titleCase(slug)
}

const ALREADY_DONE = /already started|already resolved|not pending approval|already approved|no longer pending/i

export default function ApprovalsPage() {
  return (
    <AppShell title="Approvals">
      <Suspense fallback={null}>
        <DecisionQueue />
      </Suspense>
    </AppShell>
  )
}

/** Exported for reuse in the Trust & Safety tabbed view. */
export { DecisionQueue }

function DecisionQueue() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const { mutate: mutateCache } = useSWRConfig()
  const { user } = useAuth()
  const { isAdmin, loading: adminLoading } = useOrgAdmin()
  const canApproveWrites = useMyCapability("approve_writes")
  const [tab, setTab] = useState<QueueTab>("pending")
  const [query, setQuery] = useState("")
  const [oldestFirst, setOldestFirst] = useState(true)
  const [risk, setRisk] = useState<RiskLevel | "all">("all")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [rejectTarget, setRejectTarget] = useState<Approval | null>(null)
  const [rejectReason, setRejectReason] = useState("")
  const [now, setNow] = useState(() => Date.now())
  const [lastUpdated, setLastUpdated] = useState<number | null>(null)
  const listRef = useRef<HTMLDivElement | null>(null)
  const detailRef = useRef<HTMLDivElement | null>(null)
  const itemRefs = useRef(new Map<string, HTMLButtonElement>())

  const {
    data: pendingData,
    error: pendingError,
    isValidating: pendingValidating,
    mutate: mutatePending,
  } = useSWR(user ? "/api/approvals" : null, apiFetcher, {
    revalidateOnFocus: true,
    refreshInterval: 30_000,
  })
  const {
    data: historyData,
    error: historyError,
    isValidating: historyValidating,
    mutate: mutateHistory,
  } = useSWR(user ? "/api/approvals?status=history" : null, apiFetcher, {
    revalidateOnFocus: false,
    refreshInterval: 120_000,
  })
  const refreshing = Boolean(pendingValidating || historyValidating)
  const refresh = useCallback(async () => {
    // A decision can resume or cancel a run; invalidate other mounted views
    // instead of leaving their cached execution status actionable.
    await Promise.all([
      mutatePending(),
      mutateHistory(),
      mutateCache((key) => typeof key === "string" && (
        key.startsWith("/api/runs") || key.startsWith("/api/agents") ||
        key.startsWith("/api/sessions") || key.startsWith("agent-identity-")
      )),
    ])
  }, [mutatePending, mutateHistory, mutateCache])

  useEffect(() => {
    if (pendingData) setLastUpdated(Date.now())
  }, [pendingData])
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])

  const pending = useMemo(
    () => normalizeApprovals(pendingData).filter((a) => a.status === "pending"),
    [pendingData],
  )
  const history = useMemo(
    () =>
      historyData
        ? normalizeApprovals(historyData).filter((a) => a.status === "approved" || a.status === "rejected")
        : null,
    [historyData],
  )
  const breached = useMemo(() => pending.filter((a) => isPastSla(a, now)), [pending, now])
  const approved = useMemo(() => history?.filter((a) => a.status === "approved") ?? null, [history])
  const rejected = useMemo(() => history?.filter((a) => a.status === "rejected") ?? null, [history])

  const counts: Record<QueueTab, number | null> = {
    pending: pendingData ? pending.length : null,
    breached: pendingData ? breached.length : null,
    approved: approved ? approved.length : null,
    rejected: rejected ? rejected.length : null,
  }
  const base = useMemo(
    () =>
      tab === "pending" ? pending : tab === "breached" ? breached : tab === "approved" ? approved ?? [] : rejected ?? [],
    [tab, pending, breached, approved, rejected],
  )
  const filtersOn = query.trim().length > 0 || risk !== "all"
  const visible = useMemo(() => {
    const rows = base.filter((a) => matchesQuery(a, query) && (risk === "all" || a.context.riskLevel === risk))
    const at = (a: Approval) =>
      parseTime(tab === "approved" || tab === "rejected" ? a.reviewedAt ?? a.requestedAt : a.requestedAt) ?? 0
    return [...rows].sort((x, y) => (oldestFirst ? at(x) - at(y) : at(y) - at(x)))
  }, [base, query, risk, oldestFirst, tab])

  const selected = visible.find((a) => a.id === selectedId) ?? visible[0] ?? null
  const selectedIndex = selected ? visible.indexOf(selected) : -1

  usePublishGravitreAISelection(
    selected ? { kind: "approval", id: selected.id, label: selected.title } : null,
  )

  // Deep link: /approvals?id=<approval or run id> opens that request on its tab.
  const deepLinkId = searchParams.get("id") || searchParams.get("approval")
  const deepLinked = useRef<string | null>(null)
  useEffect(() => {
    if (!deepLinkId || deepLinked.current === deepLinkId) return
    const inPending = pending.find((a) => a.id === deepLinkId)
    const inHistory = history?.find((a) => a.id === deepLinkId)
    if (!inPending && !inHistory) return
    deepLinked.current = deepLinkId
    if (inPending) setTab("pending")
    else if (inHistory) setTab(inHistory.status === "rejected" ? "rejected" : "approved")
    setSelectedId(deepLinkId)
  }, [deepLinkId, pending, history])

  const select = useCallback((id: string, focus = false) => {
    setSelectedId(id)
    const node = itemRefs.current.get(id)
    if (node) {
      node.scrollIntoView?.({ block: "nearest" })
      if (focus) node.focus({ preventScroll: true })
    }
  }, [])

  const pickTab = (next: QueueTab) => {
    setTab(next)
    setSelectedId(null)
  }

  const canDecide = (a: Approval) =>
    adminLoading || isAdmin || canApproveWrites || (isExtensionGate(a) && Boolean(user?.id) && a.requestedById === user?.id)

  const nextAfter = (id: string) => {
    const idx = visible.findIndex((a) => a.id === id)
    return visible[idx + 1]?.id ?? visible[idx - 1]?.id ?? null
  }

  const approve = async (a: Approval) => {
    if (busyId || a.status !== "pending") return
    const following = nextAfter(a.id)
    setBusyId(a.id)
    try {
      const result = (await approvalsApi.approve(a.id)) as unknown as Record<string, unknown> | null
      if (result && result.success === false) {
        toast.error(String(result.message ?? "The approved action did not run."))
        await refresh()
        return
      }
      await refresh()
      setSelectedId(following)
      const runStatus = String(result?.status ?? "")
      const runId = a.context.runId
      toast.success("Approved", {
        description:
          runStatus === "pending_approval"
            ? "Recorded. Another approver is still needed."
            : typeof result?.message === "string" && result.message
              ? result.message
              : "The paused work is continuing.",
        action: runId
          ? { label: "View run", onClick: () => router.push(`/runs/${runId}`) }
          : undefined,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not approve"
      if (ALREADY_DONE.test(message)) {
        await refresh()
        setSelectedId(following)
        toast.success("Already decided", { description: "This request is no longer waiting in the queue." })
        return
      }
      toast.error(message)
    } finally {
      setBusyId(null)
    }
  }

  const openReject = (a: Approval) => {
    if (busyId || a.status !== "pending") return
    setRejectReason("")
    setRejectTarget(a)
  }

  const reject = async () => {
    const a = rejectTarget
    const reason = rejectReason.trim()
    if (!a) return
    if (!reason) {
      toast.error("Add a reason so the requester knows what to change")
      return
    }
    const following = nextAfter(a.id)
    setBusyId(a.id)
    try {
      await approvalsApi.reject(a.id, { comment: reason })
      await refresh()
      setRejectTarget(null)
      setSelectedId(following)
      toast.success("Rejected", { description: "Nothing was run. Your reason is on the record." })
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not reject"
      if (ALREADY_DONE.test(message)) {
        await refresh()
        setRejectTarget(null)
        setSelectedId(following)
        toast.success("Already decided", { description: "This request is no longer waiting in the queue." })
        return
      }
      toast.error(message)
    } finally {
      setBusyId(null)
    }
  }

  // Keyboard: J / K move through the list, A approves, R rejects with a reason.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return
      if (rejectTarget || isTypingTarget(event.target)) return
      if (document.querySelector('[role="dialog"][data-state="open"],[role="alertdialog"],[role="menu"]')) return
      const key = event.key.toLowerCase()
      if (key === "j" || key === "k") {
        if (visible.length === 0) return
        event.preventDefault()
        const step = key === "j" ? 1 : -1
        const idx = selectedIndex < 0 ? 0 : Math.min(visible.length - 1, Math.max(0, selectedIndex + step))
        select(visible[idx].id, true)
        return
      }
      if (!selected || selected.status !== "pending" || !canDecide(selected)) return
      if (key === "a") {
        event.preventDefault()
        void approve(selected)
      } else if (key === "r") {
        event.preventDefault()
        openReject(selected)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  })

  const summary = summarySentence(pending.length, breached.length)
  const historyTab = tab === "approved" || tab === "rejected"
  const loadError = historyTab ? historyError : pendingError
  const listLoading = (historyTab ? !historyData : !pendingData) && !loadError

  const tabButton = (id: QueueTab, label: string) => {
    const n = counts[id]
    return (
      <button
        type="button"
        className={cn("gv-tab", id === "breached" && (n ?? 0) > 0 && "sla")}
        data-tab={id}
        aria-pressed={tab === id}
        onClick={() => pickTab(id)}
      >
        <span className="n">{n == null ? <span className="ov-skel-n" aria-label="Loading" /> : n}</span>
        {label}
      </button>
    )
  }
  const waitingTabs = tab === "pending" || tab === "breached"

  return (
    <WsPage className={cn("dq", selected?.status === "pending" && "dq-has-dock")}>
      <header className="dq-head">
        <div className="dq-head-copy">
          <div className="gv-eyebrow">Human in the loop</div>
          <h1>Decision queue</h1>
          <p className="dq-lead" aria-live="polite">
            {pendingData ? (
              <>
                {pending.length > 0 ? <span className="gv-ping dq-ping" aria-hidden /> : null}
                <span>
                  <strong className={cn(pending.length > 0 && "warn")}>{summary.lead}</strong>
                  {summary.rest}
                </span>
              </>
            ) : pendingError ? (
              "Could not load the queue."
            ) : (
              "Loading the queue..."
            )}
          </p>
        </div>
        <div className="dq-head-tools">
          {pendingError ? (
            <span className="dq-fresh stale" role="status">
              <i aria-hidden />
              Could not refresh
            </span>
          ) : (
            <span className="dq-fresh">
              <i aria-hidden />
              {updatedLabel(lastUpdated, now)}
            </span>
          )}
          <button
            type="button"
            className="gv-iconbtn"
            aria-label="Refresh"
            onClick={() => void refresh()}
            disabled={refreshing}
          >
            <RefreshCw size={17} aria-hidden className={cn(refreshing && "ov-spin")} />
          </button>
          <Link className="gv-btn outline" href={POLICIES_HREF}>
            Approval policies
          </Link>
        </div>
      </header>

      <nav aria-label="Queue filters" className="gv-card gv-tabs">
        {tabButton("pending", "Waiting on you")}
        {tabButton("breached", "Past SLA")}
        {tabButton("approved", "Approved")}
        {tabButton("rejected", "Rejected")}
      </nav>

      <div className="dq-split">
        <section className="dq-list" aria-label="Requests" data-review-surface="approvals-queue" ref={listRef}>
          <label className="gv-field">
            <Search size={16} aria-hidden />
            <input
              type="search"
              aria-label="Filter requests"
              placeholder="Filter by agent, app or action"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <div className="dq-list-bar">
            <button
              type="button"
              className="ov-plain"
              onClick={() => setOldestFirst((v) => !v)}
              aria-label={`Sort: ${oldestFirst ? "oldest first" : "newest first"}. Change sort order`}
            >
              {oldestFirst ? "Oldest first" : "Newest first"}
            </button>
            {tab === "breached" ? (
              <button type="button" className="ov-plain" onClick={() => pickTab("pending")}>
                Past SLA only · Show all
              </button>
            ) : null}
            <select
              className="ov-plain"
              aria-label="Filter by risk"
              value={risk}
              onChange={(e) => setRisk(e.target.value as RiskLevel | "all")}
            >
              <option value="all">Risk: all</option>
              <option value="high">Risk: high</option>
              <option value="medium">Risk: medium</option>
              <option value="low">Risk: low</option>
            </select>
          </div>

          {loadError ? (
            <div className="ov-alert" role="status">
              Could not load the latest requests. Showing what was loaded before.
            </div>
          ) : null}

          {listLoading ? (
            <div className="gv-card dq-empty" aria-label="Loading requests">
              <span>Loading requests...</span>
            </div>
          ) : visible.length === 0 && filtersOn && base.length > 0 ? (
            <div className="gv-card dq-empty">
              <b>No requests match this filter</b>
              <button
                type="button"
                className="ov-linkbtn"
                onClick={() => {
                  setQuery("")
                  setRisk("all")
                }}
              >
                Clear filters
              </button>
            </div>
          ) : (
            <>
              {visible.map((a) => (
                <RequestItem
                  key={a.id}
                  approval={a}
                  now={now}
                  selected={selected?.id === a.id}
                  onSelect={() => {
                    select(a.id)
                    if (window.matchMedia?.("(max-width: 900px)").matches) {
                      detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
                    }
                  }}
                  registerRef={(node) => {
                    if (node) itemRefs.current.set(a.id, node)
                    else itemRefs.current.delete(a.id)
                  }}
                />
              ))}
              {waitingTabs ? (
                <div className="gv-card dq-zero">
                  <WsArt
                    src={pending.length ? "/illustrations/ws-approvals-inbox-tray.svg" : "/illustrations/moment-inbox-zero.svg"}
                    alt={pending.length ? "An inbox tray of approved requests with one request left on top" : ""}
                    status={pending.length ? `${pending.length} ${pending.length === 1 ? "request" : "requests"} waiting` : "Queue clear"}
                    tone={pending.length ? "amber" : "green"}
                  />
                  <b>
                    {pending.length === 0
                      ? "Inbox zero"
                      : pending.length === 1
                        ? "One decision from inbox zero"
                        : `${pending.length} decisions from inbox zero`}
                  </b>
                  <span>New requests appear here the moment an agent pauses.</span>
                </div>
              ) : visible.length === 0 ? (
                <div className="gv-card dq-empty">
                  <b>{tab === "approved" ? "Nothing approved yet" : "Nothing rejected"}</b>
                  <span>
                    {tab === "approved"
                      ? "Approved requests and who decided them will show here."
                      : "Rejected requests and the reasons given will show here."}
                  </span>
                </div>
              ) : null}
            </>
          )}
        </section>

        <div className="dq-detail" ref={detailRef}>
          {selected ? (
            <DetailPane
              key={selected.id}
              approval={selected}
              now={now}
              busy={busyId === selected.id}
              canDecide={canDecide(selected)}
              onApprove={() => void approve(selected)}
              onReject={() => openReject(selected)}
              onBack={() => listRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
              approvedCount={counts.approved}
              onHistory={() => pickTab("approved")}
            />
          ) : listLoading ? null : (
            <div className="gv-card dq-placeholder">
              <b>{waitingTabs ? "Nothing is waiting on you" : "Pick a request to see the details"}</b>
              <span>
                {waitingTabs
                  ? "When an agent pauses for a decision it lands here, oldest first."
                  : "The plan, the risk and who decided appear here."}
              </span>
            </div>
          )}
        </div>
      </div>

      {selected?.status === "pending" && canDecide(selected) ? (
        <div className="dq-dock" data-testid="approval-mobile-actions" data-gravitre-mobile-action-dock>
          <button
            type="button"
            className="ov-btn dark"
            data-review-cta="approve"
            disabled={Boolean(busyId)}
            onClick={() => void approve(selected)}
          >
            Approve
          </button>
          <button
            type="button"
            className="ov-btn danger"
            disabled={Boolean(busyId)}
            onClick={() => openReject(selected)}
          >
            Reject
          </button>
        </div>
      ) : null}

      <AlertDialog open={Boolean(rejectTarget)} onOpenChange={(open) => !open && !busyId && setRejectTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reject this request?</AlertDialogTitle>
            <AlertDialogDescription>
              Nothing will run. Tell the requester why, so they know what to change.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <Textarea
            aria-label="Reason for rejecting"
            placeholder="For example: wrong list, use the Q3 segment instead"
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            autoFocus
            rows={4}
          />
          <AlertDialogFooter>
            <AlertDialogCancel disabled={Boolean(busyId)}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={Boolean(busyId) || !rejectReason.trim()}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={(e) => {
                e.preventDefault()
                void reject()
              }}
            >
              {busyId ? "Rejecting..." : "Reject"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </WsPage>
  )
}

function RequestItem({
  approval: a,
  now,
  selected,
  onSelect,
  registerRef,
}: {
  approval: Approval
  now: number
  selected: boolean
  onSelect: () => void
  registerRef: (node: HTMLButtonElement | null) => void
}) {
  const sla = slaLine(a, now)
  const env = environmentLabel(a.environment)
  const decided = a.status !== "pending"
  const level = a.context.riskLevel
  const tool = a.context.tool || a.context.action
  const meta = decided
    ? [a.status === "approved" ? "Approved" : "Rejected", formatDate(a.reviewedAt ?? a.requestedAt, now)]
    : [sla ? sla.text : "Waiting", sla ? null : formatDate(a.requestedAt, now)]
  return (
    <button
      type="button"
      ref={registerRef}
      className="gv-item dq-item"
      aria-current={selected ? "true" : undefined}
      data-path-waiting={a.status === "pending" ? "1" : "0"}
      data-path-run-id={a.context.runId ?? undefined}
      onClick={onSelect}
    >
      <span className={cn("dq-item-meta", sla?.breached && "hot")}>
        {sla?.breached ? <AlertTriangle size={14} aria-hidden /> : null}
        {meta.filter(Boolean).join(" · ")}
      </span>
      <span className="dq-item-t">{a.title}</span>
      {tool ? <span className="dq-item-tool">{tool}</span> : null}
      <span className="dq-chips">
        {env ? <span className={cn("gv-pill", a.environment === "production" ? "brand" : "neutral")}>{env}</span> : null}
        {level ? <span className={cn("gv-pill", RISK_TONE[level])}>{riskLabel(level)}</span> : null}
        <span className="gv-pill neutral">{typeLabel(a)}</span>
      </span>
      <span className="dq-item-by">
        <span className="dq-ava" aria-hidden>
          {initialsOf(a.requestedBy)}
        </span>
        {[a.requestedBy, formatDate(a.requestedAt, now)].filter(Boolean).join(" · ")}
      </span>
    </button>
  )
}

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return "?"
  return (parts.length === 1 ? parts[0].slice(0, 2) : `${parts[0][0]}${parts[parts.length - 1][0]}`).toUpperCase()
}

function DetailPane({
  approval: a,
  now,
  busy,
  canDecide,
  onApprove,
  onReject,
  onBack,
  approvedCount,
  onHistory,
}: {
  approval: Approval
  now: number
  busy: boolean
  canDecide: boolean
  onApprove: () => void
  onReject: () => void
  onBack: () => void
  approvedCount: number | null
  onHistory: () => void
}) {
  const pending = a.status === "pending"
  const pastSla = isPastSla(a, now)
  const runId = a.context.runId
  const conversationId = a.context.conversationId
  const rows = whatWillHappen(a)
  const policy = policyCopy(a)
  const events = activity(a, now)
  const sla = slaLine(a, now)
  const raw = useMemo(() => {
    try {
      return JSON.stringify(a.rawRequest, null, 2)
    } catch {
      return "{}"
    }
  }, [a.rawRequest])

  const copyLink = async () => {
    const url = `${window.location.origin}/approvals?id=${encodeURIComponent(a.id)}`
    try {
      await navigator.clipboard.writeText(url)
      toast.success("Link copied")
    } catch {
      toast.error("Could not copy the link")
    }
  }

  return (
    <article className="gv-card gv-rise dq-card" aria-label={a.title} data-review-surface="approvals-inspect">
      <button type="button" className="ov-linkbtn ov-back" onClick={onBack}>
        Back to the list
      </button>
      <div className={cn("dq-card-head", pending ? "waiting" : a.status)}>
        <div className="dq-card-copy">
          <div className="dq-chips">
            {pending ? (
              <span className="gv-pill amber">
                <span className="gv-ping dq-ping sm" aria-hidden />
                Waiting on you
              </span>
            ) : a.status === "approved" ? (
              <span className="gv-pill brand">
                <Check size={14} strokeWidth={2.6} aria-hidden />
                Approved
              </span>
            ) : (
              <span className="gv-pill red">Rejected</span>
            )}
            {pending && pastSla ? <span className="gv-pill red">SLA breached</span> : null}
          </div>
          <h2>{a.title}</h2>
          {a.description ? <p>{a.description}</p> : null}
        </div>
        <WsArt
          className="gv-hide-sm dq-card-art"
          src="/illustrations/ws-approvals-request-waiting.svg"
          alt="A person thinking at their desk while a request waits"
          status={pending ? sla?.text ?? "Waiting" : decidedByLine(a, now)}
          tone={pending ? (pastSla ? "red" : "amber") : a.status === "approved" ? "green" : "red"}
        />
      </div>

      <div className="dq-actions">
        {pending ? (
          <>
            <button
              type="button"
              className="gv-btn primary"
              data-review-cta="approve"
              disabled={busy || !canDecide}
              onClick={onApprove}
            >
              {busy ? "Working..." : "Approve"} <span className="gv-kbd">A</span>
            </button>
            <button type="button" className="gv-btn danger" disabled={busy || !canDecide} onClick={onReject}>
              Reject <span className="gv-kbd">R</span>
            </button>
          </>
        ) : null}
        {runId ? (
          <Link className={cn("gv-btn", pending ? "outline" : "primary")} href={`/runs/${encodeURIComponent(runId)}`}>
            View the run
          </Link>
        ) : null}
        <AskGravitreSummonButton
          className="gv-btn outline"
          selected={{ kind: "approval", id: a.id, label: a.title }}
          label="Ask Gravitre about this"
        />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button type="button" className="gv-iconbtn dq-more" aria-label="More actions">
              <MoreHorizontal size={18} aria-hidden />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            {conversationId ? (
              <DropdownMenuItem asChild>
                <Link href={`/ai?c=${encodeURIComponent(conversationId)}`}>Open the conversation</Link>
              </DropdownMenuItem>
            ) : null}
            <DropdownMenuItem onSelect={() => void copyLink()}>Copy link to this request</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        {pending ? (
          <p className="dq-lock">
            <Lock size={14} aria-hidden />
            {canDecide ? lockNote(a) : "Only workspace admins can decide this request."}
          </p>
        ) : a.reviewComment ? (
          <p className="dq-lock">Reason given: &ldquo;{a.reviewComment}&rdquo;</p>
        ) : null}
      </div>

      <div className="dq-cols">
        <section>
          <h3>What will happen</h3>
          {rows.length ? (
            <dl className="gv-dl">
              {rows.map((r) => (
                <Fragment key={r.term}>
                  <dt>{r.term}</dt>
                  <dd className={cn(r.mono && "gv-mono")}>{r.href ? <Link href={r.href}>{r.value}</Link> : r.value}</dd>
                </Fragment>
              ))}
            </dl>
          ) : (
            <p className="dq-muted">
              The request did not describe its action. The raw request below has everything that was sent.
            </p>
          )}
          {a.steps.length ? (
            <ol className="dq-steps" aria-label="What the agent asked to do">
              {a.steps.map((st, i) => (
                <li key={`${i}-${st.text}`}>
                  <span className="n">{i + 1}</span>
                  <span className="b">
                    <b>{st.text}</b>
                    <span>{appName(st.app)}</span>
                  </span>
                  <span className={cn("gv-pill", st.access === "write" ? "amber" : "neutral")}>
                    {st.access === "write" ? "Write" : "Read"}
                  </span>
                </li>
              ))}
            </ol>
          ) : null}
          <details className="dq-raw">
            <summary>
              View raw request <span>JSON</span>
            </summary>
            <pre>{raw}</pre>
          </details>
        </section>
        <section>
          <h3>Why it paused</h3>
          <div className="dq-policy">
            <ShieldCheck size={20} aria-hidden />
            <div>
              <strong>{policy?.title ?? policyLine(a)}</strong>
              {policy?.body ? <div>{policy.body}</div> : null}
              {a.context.riskLevel ? <div>{riskLabel(a.context.riskLevel)}.</div> : null}
              <Link href={POLICIES_HREF}>Review policy →</Link>
            </div>
          </div>
          <h3 className="dq-gap">Activity</h3>
          <ol className="dq-timeline">
            {events.map((e) => (
              <li key={e.key} className={e.tone}>
                <span className="dot" aria-hidden />
                <div className="t">{e.title}</div>
                {e.detail ? <div className="d">{e.detail}</div> : null}
              </li>
            ))}
          </ol>
        </section>
      </div>

      <div className="dq-foot">
        <span>
          <span className="gv-kbd">J</span> <span className="gv-kbd">K</span> Next and previous
        </span>
        {pending ? (
          <>
            <span>
              <span className="gv-kbd">A</span> Approve
            </span>
            <span>
              <span className="gv-kbd">R</span> Reject with a reason
            </span>
          </>
        ) : null}
        {approvedCount != null ? (
          <button type="button" className="dq-history" onClick={onHistory}>
            {approvedCount} approved · View history →
          </button>
        ) : null}
      </div>
    </article>
  )
}
