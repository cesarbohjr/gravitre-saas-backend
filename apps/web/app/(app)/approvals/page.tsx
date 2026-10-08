"use client"

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { useRouter, useSearchParams } from "next/navigation"
import { toast } from "sonner"
import { AlertTriangle, Lock, MoreHorizontal, RefreshCw, Search, ShieldCheck } from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { Illustration } from "@/components/gravitre/illustration"
import { WsPage } from "@/components/workspace/ws-page"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { approvalsApi } from "@/lib/api"
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
  activity,
  environmentLabel,
  formatDate,
  isExtensionGate,
  isPastSla,
  lockNote,
  matchesQuery,
  normalizeApprovals,
  parseTime,
  policyCopy,
  slaLine,
  summarySentence,
  typeLabel,
  whatWillHappen,
  type Approval,
  type QueueTab,
  type RiskLevel,
} from "@/components/approvals/decision-queue/model"
import "@/components/approvals/decision-queue/decision-queue.css"

const POLICIES_HREF = "/settings/approvals"

const TABS: Array<{ id: QueueTab; label: string }> = [
  { id: "pending", label: "Waiting on you" },
  { id: "breached", label: "Past SLA" },
  { id: "approved", label: "Approved" },
  { id: "rejected", label: "Rejected" },
]

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return "?"
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

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

function DecisionQueue() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const { user } = useAuth()
  const { isAdmin, loading: adminLoading } = useOrgAdmin()
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
  const listRef = useRef<HTMLElement | null>(null)
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
    await Promise.all([mutatePending(), mutateHistory()])
  }, [mutatePending, mutateHistory])

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
    if (inPending) setTab(isPastSla(inPending) ? "breached" : "pending")
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

  const canDecide = (a: Approval) =>
    adminLoading || isAdmin || (isExtensionGate(a) && Boolean(user?.id) && a.requestedById === user?.id)

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
  const loadError = tab === "approved" || tab === "rejected" ? historyError : pendingError
  const listLoading = (tab === "approved" || tab === "rejected" ? !historyData : !pendingData) && !loadError

  return (
    <WsPage className={cn(selected?.status === "pending" && "dq-has-dock")}>
      <header className="dq-head">
        <div className="dq-head-main">
          <div className="gv-eyebrow">Human in the loop</div>
          <h1 className="dq-title">Decision queue</h1>
          {pendingData ? (
            <p className={cn("dq-summary", pending.length === 0 && "calm")} aria-live="polite">
              {pending.length > 0 ? (
                <span
                  className="gv-ping"
                  style={{ background: "var(--gv-amber)", width: 9, height: 9 }}
                  aria-hidden
                />
              ) : null}
              <span>
                <strong>{summary.lead}</strong>
                {summary.rest}
              </span>
            </p>
          ) : (
            <p className="dq-summary">{pendingError ? "Could not load the queue." : "Loading the queue..."}</p>
          )}
        </div>
        <div className="dq-head-actions">
          <span className={cn("dq-fresh", pendingError && "stale")}>
            <span className="gv-dot" aria-hidden />
            {pendingError ? "Could not refresh" : updatedLabel(lastUpdated, now)}
          </span>
          <button
            type="button"
            className="gv-iconbtn"
            aria-label="Refresh"
            onClick={() => void refresh()}
            disabled={refreshing}
          >
            <RefreshCw size={18} className={cn(refreshing && "dq-spin")} aria-hidden />
          </button>
          <Link className="gv-btn outline" href={POLICIES_HREF}>
            Approval policies
          </Link>
        </div>
      </header>

      <nav aria-label="Queue filters" className="gv-card dq-tabs">
        {TABS.map((t) => {
          const n = counts[t.id]
          return (
            <button
              key={t.id}
              type="button"
              className={cn("dq-tab", tab === t.id && "on", t.id === "breached" && (n ?? 0) > 0 && "sla")}
              aria-current={tab === t.id ? "true" : undefined}
              data-tab={t.id}
              onClick={() => {
                setTab(t.id)
                setSelectedId(null)
              }}
            >
              <span className={cn("n", t.id === "breached" && (n ?? 0) > 0 && "hot")}>
                {n == null ? <span className="gv-skel" aria-label="Loading" /> : n}
              </span>
              {t.label}
            </button>
          )
        })}
      </nav>

      {loadError ? (
        <div className="dq-error" role="status">
          <AlertTriangle size={16} aria-hidden />
          Could not load the latest requests. Showing what was loaded before.
        </div>
      ) : null}

      <div className="dq-body">
        <section
          aria-label="Requests"
          className="dq-list"
          data-review-surface="approvals-queue"
          ref={(node) => {
            listRef.current = node
          }}
        >
          <label className="gv-field">
            <Search size={18} aria-hidden />
            <input
              aria-label="Filter requests"
              placeholder="Filter by agent, app or action"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <div className="dq-listbar">
            <button
              type="button"
              className="dq-plain"
              onClick={() => setOldestFirst((v) => !v)}
              aria-label={`Sort: ${oldestFirst ? "oldest first" : "newest first"}. Change sort order`}
            >
              {oldestFirst ? "Oldest first" : "Newest first"}
            </button>
            <select
              className="dq-plain"
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

          {listLoading ? (
            <div className="gv-card" style={{ padding: 16 }} aria-label="Loading requests">
              <div className="gv-skel" style={{ width: "40%" }} />
              <div className="gv-skel" style={{ width: "80%", marginTop: 12, height: 14 }} />
              <div className="gv-skel" style={{ width: "60%", marginTop: 12 }} />
            </div>
          ) : null}

          {visible.map((a) => (
            <RequestCard
              key={a.id}
              approval={a}
              now={now}
              selected={selected?.id === a.id}
              onSelect={() => select(a.id)}
              registerRef={(node) => {
                if (node) itemRefs.current.set(a.id, node)
                else itemRefs.current.delete(a.id)
              }}
            />
          ))}

          {!listLoading && visible.length === 0 && filtersOn && base.length > 0 ? (
            <div className="gv-empty">
              No requests match this filter.{" "}
              <button
                type="button"
                className="dq-linkbtn"
                onClick={() => {
                  setQuery("")
                  setRisk("all")
                }}
              >
                Clear filters
              </button>
            </div>
          ) : null}

          {!listLoading && tab === "pending" && pending.length <= 1 && !pendingError ? (
            <div className="gv-card dq-zero">
              <Illustration name="moment-inbox-zero" width={320} />
              <div className="dq-zero-title">
                {pending.length === 1 ? "One decision from inbox zero" : "Inbox zero"}
              </div>
              <div className="dq-zero-body">New requests appear here the moment an agent pauses.</div>
            </div>
          ) : null}

          {!listLoading && base.length === 0 && tab !== "pending" ? (
            <div className="gv-empty">
              {tab === "breached"
                ? "No request is past its SLA."
                : tab === "approved"
                  ? "No approved requests yet."
                  : "No rejected requests yet."}
            </div>
          ) : null}
        </section>

        {selected ? (
          <DetailPane
            key={selected.id}
            approval={selected}
            now={now}
            busy={busyId === selected.id}
            canDecide={canDecide(selected)}
            approvedCount={counts.approved}
            onApprove={() => void approve(selected)}
            onReject={() => openReject(selected)}
            onViewHistory={() => {
              setTab("approved")
              setSelectedId(null)
            }}
            onBack={() => listRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
          />
        ) : !listLoading ? (
          <article className="gv-card dq-detail" style={{ padding: "28px" }}>
            <h2 className="gv-h2">{tab === "pending" ? "Nothing to decide right now" : "Nothing selected"}</h2>
            <p className="gv-hint" style={{ marginTop: 8 }}>
              {tab === "pending" || tab === "breached"
                ? "When an agent or workflow needs your decision before it changes a connected system, the request lands here."
                : "Decided requests stay here with who decided and when."}
            </p>
            {tab !== "approved" ? (
              <button
                type="button"
                className="gv-btn outline sm"
                style={{ marginTop: 16 }}
                onClick={() => {
                  setTab("approved")
                  setSelectedId(null)
                }}
              >
                View history
              </button>
            ) : null}
          </article>
        ) : null}
      </div>

      {selected?.status === "pending" && canDecide(selected) ? (
        <div className="dq-dock" data-testid="approval-mobile-actions" data-gravitre-mobile-action-dock>
          <button
            type="button"
            className="gv-btn primary"
            data-review-cta="approve"
            disabled={Boolean(busyId)}
            onClick={() => void approve(selected)}
          >
            Approve
          </button>
          <button
            type="button"
            className="gv-btn danger"
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

function RequestCard({
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
  return (
    <button
      type="button"
      ref={registerRef}
      className={cn("dq-item", selected && "on", decided && "done")}
      aria-current={selected ? "true" : undefined}
      data-path-waiting={a.status === "pending" ? "1" : "0"}
      data-path-run-id={a.context.runId ?? undefined}
      onClick={onSelect}
    >
      {decided ? (
        <div className="dq-item-sla quiet">
          {a.status === "approved" ? "Approved" : "Rejected"}
          {formatDate(a.reviewedAt, now) ? ` · ${formatDate(a.reviewedAt, now)}` : ""}
        </div>
      ) : sla ? (
        <div className={cn("dq-item-sla", sla.breached && "hot")}>
          {sla.breached ? <AlertTriangle size={14} aria-hidden /> : null}
          {sla.text}
        </div>
      ) : null}
      <div className="dq-item-title">{a.title}</div>
      {a.context.tool ? <div className="dq-item-tool">{a.context.tool}</div> : null}
      <div className="dq-pills">
        {env ? <span className={cn("gv-pill", a.environment === "production" ? "brand" : "neutral")}>{env}</span> : null}
        {a.context.riskLevel ? (
          <span
            className={cn(
              "gv-pill",
              a.context.riskLevel === "high" ? "red" : a.context.riskLevel === "medium" ? "amber" : "neutral",
            )}
          >
            {a.context.riskLevel.charAt(0).toUpperCase() + a.context.riskLevel.slice(1)} risk
          </span>
        ) : null}
        <span className="gv-pill neutral">{typeLabel(a)}</span>
      </div>
      <div className="dq-who">
        <span className="dq-ini" aria-hidden>
          {initials(a.requestedBy)}
        </span>
        {[a.requestedBy, formatDate(a.requestedAt, now)].filter(Boolean).join(" · ")}
      </div>
    </button>
  )
}

function DetailPane({
  approval: a,
  now,
  busy,
  canDecide,
  approvedCount,
  onApprove,
  onReject,
  onViewHistory,
  onBack,
}: {
  approval: Approval
  now: number
  busy: boolean
  canDecide: boolean
  approvedCount: number | null
  onApprove: () => void
  onReject: () => void
  onViewHistory: () => void
  onBack: () => void
}) {
  const pending = a.status === "pending"
  const pastSla = isPastSla(a, now)
  const rows = whatWillHappen(a)
  const policy = policyCopy(a)
  const events = activity(a, now)
  const raw = useMemo(() => {
    try {
      return JSON.stringify(a.rawRequest, null, 2)
    } catch {
      return "{}"
    }
  }, [a.rawRequest])
  const runId = a.context.runId
  const conversationId = a.context.conversationId

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
    <article
      className="gv-card gv-rise dq-detail"
      aria-label={a.title}
      data-review-surface="approvals-inspect"
    >
      <div className={cn("dq-hero", !pending && "done")}>
        <div className="dq-hero-main">
          <button type="button" className="dq-linkbtn dq-back" onClick={onBack}>
            Back to the list
          </button>
          <div className="dq-pills" style={{ marginTop: 0 }}>
            {pending ? (
              <span className="gv-pill amber">
                <span className="gv-ping" style={{ background: "var(--gv-amber)", width: 7, height: 7 }} aria-hidden />
                Waiting on you
              </span>
            ) : a.status === "approved" ? (
              <span className="gv-pill brand">Approved</span>
            ) : (
              <span className="gv-pill red">Rejected</span>
            )}
            {pastSla ? <span className="gv-pill red">SLA breached</span> : null}
          </div>
          <h2>{a.title}</h2>
          {a.description ? <p>{a.description}</p> : null}
        </div>
        {pending ? (
          <div className="gv-hide-sm">
            <Illustration name="moment-request-waiting" width={200} className="dq-hero-art" />
          </div>
        ) : null}
      </div>

      {pending ? (
        <div className="dq-actions">
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
          <MoreMenu runId={runId} conversationId={conversationId} onCopy={copyLink} />
          <div className="dq-lock">
            <Lock size={14} aria-hidden />
            {canDecide ? lockNote(a) : "Only workspace admins can decide this request."}
          </div>
        </div>
      ) : (
        <div className="dq-actions">
          {runId ? (
            <Link className="gv-btn outline" href={`/runs/${encodeURIComponent(runId)}`}>
              View the run
            </Link>
          ) : null}
          {a.reviewComment ? (
            <span className="gv-hint">Reason given: &ldquo;{a.reviewComment}&rdquo;</span>
          ) : null}
          <MoreMenu runId={runId} conversationId={conversationId} onCopy={copyLink} />
        </div>
      )}

      <div className="dq-cols">
        <section className="dq-col">
          <h3>{pending ? "What will happen" : "What was requested"}</h3>
          {rows.length ? (
            <dl className="gv-dl">
              {rows.map((row) => (
                <div key={row.term} style={{ display: "contents" }}>
                  <dt>{row.term}</dt>
                  <dd className={cn(row.mono && "gv-mono")}>
                    {row.href ? <Link href={row.href}>{row.value}</Link> : row.value}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="gv-hint">The request did not include any details beyond its title.</p>
          )}
          <details className="dq-raw">
            <summary>
              View raw request <span>JSON</span>
            </summary>
            <pre>{raw}</pre>
          </details>
        </section>
        <section className="dq-col">
          <h3>Why it paused</h3>
          {policy ? (
            <div className="dq-policy">
              <ShieldCheck size={20} aria-hidden />
              <div>
                <strong>{policy.title}</strong>
                <div className="sub">{policy.body}</div>
                {a.context.approvalReason ? <div className="sub">{a.context.approvalReason}</div> : null}
                <Link href={POLICIES_HREF}>Review policy &rarr;</Link>
              </div>
            </div>
          ) : (
            <div className="dq-policy">
              <ShieldCheck size={20} aria-hidden />
              <div>
                <strong>{a.context.approvalReason ?? "This request needs a person to decide before it runs."}</strong>
                <div className="sub">The policy that paused it was not reported.</div>
                <Link href={POLICIES_HREF}>Review policies &rarr;</Link>
              </div>
            </div>
          )}
          <h3 className="next">Activity</h3>
          <ol className="dq-timeline">
            {events.map((e) => (
              <li key={e.key}>
                <span className={cn("mk", e.tone)} aria-hidden />
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
        <span className="end">
          <AskGravitreSummonButton
            selected={{ kind: "approval", id: a.id, label: a.title }}
            label="Ask Gravitre about this"
          />
          <button type="button" className="dq-linkbtn" onClick={onViewHistory}>
            {approvedCount != null ? `${approvedCount} approved · ` : ""}View history &rarr;
          </button>
        </span>
      </div>
    </article>
  )
}

function MoreMenu({
  runId,
  conversationId,
  onCopy,
}: {
  runId: string | null
  conversationId: string | null
  onCopy: () => void
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" className="gv-iconbtn dq-more" aria-label="More actions">
          <MoreHorizontal size={18} aria-hidden />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        {runId ? (
          <DropdownMenuItem asChild>
            <Link href={`/runs/${encodeURIComponent(runId)}`}>Open the run</Link>
          </DropdownMenuItem>
        ) : null}
        {conversationId ? (
          <DropdownMenuItem asChild>
            <Link href={`/ai?c=${encodeURIComponent(conversationId)}`}>Open the conversation</Link>
          </DropdownMenuItem>
        ) : null}
        <DropdownMenuItem onSelect={() => onCopy()}>Copy link to this request</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
