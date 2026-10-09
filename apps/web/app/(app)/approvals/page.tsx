"use client"

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { useRouter, useSearchParams } from "next/navigation"
import { toast } from "sonner"
import { Check, MoreHorizontal, RefreshCw, Search, Shield } from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { WsPage } from "@/components/workspace/ws-page"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
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
  matchesQuery,
  normalizeApprovals,
  parseTime,
  policyLine,
  riskLabel,
  slaLine,
  summarySentence,
  titleCase,
  typeLabel,
  type Approval,
  type QueueTab,
  type RiskLevel,
} from "@/components/approvals/decision-queue/model"
import "@/components/workspace/ops-v4.css"

const POLICIES_HREF = "/settings/approvals"

/** The inbox switches between three queues; Past SLA is a view of Waiting, picked from its stat. */
const SEGMENTS: Array<{ id: Exclude<QueueTab, "breached">; label: string }> = [
  { id: "pending", label: "Waiting" },
  { id: "approved", label: "Approved" },
  { id: "rejected", label: "Rejected" },
]

const RISK_TONE: Record<RiskLevel, string> = { low: "green", medium: "amber", high: "red" }

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
  const historyTab = tab === "approved" || tab === "rejected"
  const loadError = historyTab ? historyError : pendingError
  const listLoading = (historyTab ? !historyData : !pendingData) && !loadError
  const segment = tab === "breached" ? "pending" : tab

  const stat = (id: QueueTab, label: string, tone?: "green" | "red") => {
    const n = counts[id]
    return (
      <button
        type="button"
        className={cn("ov-stat", tone)}
        data-tab={id}
        aria-pressed={tab === id}
        onClick={() => pickTab(id)}
      >
        <span className="v">{n == null ? <span className="ov-skel-n" aria-label="Loading" /> : n}</span>
        <span className="k">{label}</span>
      </button>
    )
  }

  return (
    <WsPage wide={false} className={cn(selected?.status === "pending" && "dq-has-dock")}>
      <div className="ov-page">
        <section aria-labelledby="ap-hero" className="ov-hero">
          <div className="ov-hero-art">
            {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
            <img src="/illustrations/ops-approvals.svg" alt="" />
          </div>
          <div className="ov-hero-copy">
            <div className="ov-hero-eb">
              <span className="ov-eyebrow">Human in the loop</span>
              {pendingError ? (
                <span className="ov-fresh stale" role="status">
                  <i aria-hidden />
                  Could not refresh
                  <button type="button" onClick={() => void refresh()}>
                    Retry
                  </button>
                </span>
              ) : (
                <span className="ov-fresh">
                  <i aria-hidden />
                  {updatedLabel(lastUpdated, now)}
                </span>
              )}
            </div>
            <h1 id="ap-hero">Decision queue</h1>
            <p className="ov-lead" aria-live="polite">
              {pendingData ? (
                <>
                  <strong>{summary.lead}</strong>
                  {summary.rest}
                </>
              ) : pendingError ? (
                "Could not load the queue."
              ) : (
                "Loading the queue..."
              )}
            </p>
            <div className="ov-stats">
              {stat("pending", "Waiting on you", "green")}
              {stat("breached", "Past SLA", (counts.breached ?? 0) > 0 ? "red" : undefined)}
              {stat("approved", "Approved")}
              {stat("rejected", "Rejected")}
            </div>
            <div className="ov-actions">
              <Link className="ov-btn dark" href={POLICIES_HREF}>
                <Shield size={16} aria-hidden />
                Approval policies
              </Link>
              <button type="button" className="ov-btn" onClick={() => void refresh()} disabled={refreshing}>
                <RefreshCw size={16} aria-hidden className={cn(refreshing && "ov-spin")} />
                Refresh
              </button>
            </div>
          </div>
        </section>

        <section aria-labelledby="inbox-heading" className="ov-panel">
          <div className="ov-band">
            <div className="ov-band-l">
              <span className="ov-dots" aria-hidden>
                <i />
                <i />
                <i />
              </span>
              <h2 id="inbox-heading">Decision inbox</h2>
            </div>
            <div role="group" aria-label="Queue" className="ov-seg">
              {SEGMENTS.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  aria-pressed={segment === s.id}
                  onClick={() => pickTab(s.id)}
                >
                  {s.label} <span className="c">{counts[s.id] ?? ""}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="ov-split">
            <div className="ov-list" data-review-surface="approvals-queue" ref={listRef}>
              <div className="ov-list-tools">
                <label className="ov-search">
                  <Search size={15} aria-hidden />
                  <span className="ov-sr">Filter requests</span>
                  <input
                    type="search"
                    aria-label="Filter requests"
                    placeholder="Filter by agent, app or action"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </label>
                <div className="ov-list-bar">
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
              </div>

              {loadError ? (
                <div className="ov-alert" role="status" style={{ margin: 14 }}>
                  Could not load the latest requests. Showing what was loaded before.
                </div>
              ) : null}

              {listLoading ? (
                <div className="ov-empty" aria-label="Loading requests">
                  <span>Loading requests...</span>
                </div>
              ) : visible.length === 0 ? (
                <div className="ov-empty">
                  {filtersOn && base.length > 0 ? (
                    <>
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
                    </>
                  ) : (
                    <>
                      <span className="ic" aria-hidden>
                        <Check size={24} />
                      </span>
                      <b>
                        {tab === "pending"
                          ? "Inbox zero"
                          : tab === "breached"
                            ? "Nothing past its SLA"
                            : tab === "approved"
                              ? "Nothing approved yet"
                              : "Nothing rejected"}
                      </b>
                      <span>
                        {tab === "pending" || tab === "breached"
                          ? "When an agent pauses for a decision it lands here, oldest first."
                          : tab === "approved"
                            ? "Approved requests and who decided them will show here."
                            : "Rejected requests and the reasons given will show here."}
                      </span>
                    </>
                  )}
                </div>
              ) : (
                <div className="ov-items">
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
                </div>
              )}
            </div>

            <div className="ov-detail" ref={detailRef}>
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
                />
              ) : (
                <div className="ov-placeholder">
                  <b>Pick a request to see the details</b>
                  <span>The plan, the risk and who decided appear here.</span>
                </div>
              )}
            </div>
          </div>
        </section>

        <RiskLadder pending={pending} history={history} />
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
  const meta = decided
    ? [a.status === "approved" ? "Approved" : "Rejected", formatDate(a.reviewedAt ?? a.requestedAt, now)]
    : [sla ? sla.text : "Waiting", sla ? null : formatDate(a.requestedAt, now)]
  return (
    <button
      type="button"
      ref={registerRef}
      className="ov-item dq-item"
      aria-current={selected ? "true" : undefined}
      data-path-waiting={a.status === "pending" ? "1" : "0"}
      data-path-run-id={a.context.runId ?? undefined}
      onClick={onSelect}
    >
      <span className={cn("meta", sla?.breached && "hot")}>{meta.filter(Boolean).join(" · ")}</span>
      <span className="t">{a.title}</span>
      <span className="ov-chips">
        {selected && env ? (
          <span className={cn("ov-chip", a.environment === "production" && "green")}>{env}</span>
        ) : null}
        <span className="ov-chip">{typeLabel(a)}</span>
        {level ? <span className={cn("ov-chip", RISK_TONE[level])}>{riskLabel(level)}</span> : null}
      </span>
    </button>
  )
}

function DetailPane({
  approval: a,
  now,
  busy,
  canDecide,
  onApprove,
  onReject,
  onBack,
}: {
  approval: Approval
  now: number
  busy: boolean
  canDecide: boolean
  onApprove: () => void
  onReject: () => void
  onBack: () => void
}) {
  const pending = a.status === "pending"
  const pastSla = isPastSla(a, now)
  const runId = a.context.runId
  const conversationId = a.context.conversationId
  const steps = a.steps
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
    <article className="ov-detail-in" aria-label={a.title} data-review-surface="approvals-inspect">
      <button type="button" className="ov-linkbtn ov-back" onClick={onBack}>
        Back to the list
      </button>
      <div className="ov-detail-top">
        <span className="ov-chips">
          {pending ? (
            <span className={cn("ov-pill", pastSla ? "red" : "amber")}>
              <span className="ov-dot" aria-hidden />
              {pastSla ? "Past SLA" : "Waiting on you"}
            </span>
          ) : a.status === "approved" ? (
            <span className="ov-pill green">
              <Check size={14} strokeWidth={2.6} aria-hidden />
              Approved
            </span>
          ) : (
            <span className="ov-pill red">Rejected</span>
          )}
        </span>
        <span className="ov-from">
          Request from <strong>{a.requestedBy}</strong>
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <h3>{a.title}</h3>
        {a.description ? <p className="desc">{a.description}</p> : null}
        {pending ? <p className="desc">{slaLine(a, now)?.text}</p> : null}
      </div>

      <div className="ov-box">
        <div className="ov-box-head">
          <b>What the agent asked to do</b>
          <span>
            {steps.length} {steps.length === 1 ? "step" : "steps"}
          </span>
        </div>
        {steps.length ? (
          steps.map((st, i) => (
            <div className="ov-step" key={`${i}-${st.text}`}>
              <span className="n">{i + 1}</span>
              <span className="b">
                <b>{st.text}</b>
                <span>{appName(st.app)}</span>
              </span>
              <span className={cn("ov-access", st.access === "write" && "write")}>
                {st.access === "write" ? "Write" : "Read"}
              </span>
            </div>
          ))
        ) : (
          <div className="ov-step">
            <span className="b">
              <span>The request did not list its steps. The raw request below has everything that was sent.</span>
            </span>
          </div>
        )}
      </div>

      <div className="ov-facts">
        <div className="ov-fact">
          <span>Decided by</span>
          <b>{decidedByLine(a, now)}</b>
        </div>
        <div className="ov-fact">
          <span>Policy applied</span>
          <b>{policyLine(a)}</b>
        </div>
        <div className="ov-fact">
          <span>Risk</span>
          <b>{riskLabel(a.context.riskLevel)}</b>
        </div>
      </div>

      {a.reviewComment ? <p className="ov-note">Reason given: &ldquo;{a.reviewComment}&rdquo;</p> : null}
      {pending ? <p className="ov-note">{canDecide ? lockNote(a) : "Only workspace admins can decide this request."}</p> : null}

      <details className="ov-raw">
        <summary>View raw request</summary>
        <pre>{raw}</pre>
      </details>

      <div className="ov-foot">
        <div className="ov-actions">
          {pending ? (
            <>
              <button
                type="button"
                className="ov-btn dark"
                data-review-cta="approve"
                disabled={busy || !canDecide}
                onClick={onApprove}
              >
                {busy ? "Working..." : "Approve"} <span className="ov-kbd">A</span>
              </button>
              <button type="button" className="ov-btn danger" disabled={busy || !canDecide} onClick={onReject}>
                Reject <span className="ov-kbd">R</span>
              </button>
            </>
          ) : runId ? (
            <Link className="ov-btn dark" href={`/runs/${encodeURIComponent(runId)}`}>
              View the run
            </Link>
          ) : null}
          {pending && runId ? (
            <Link className="ov-btn" href={`/runs/${encodeURIComponent(runId)}`}>
              View the run
            </Link>
          ) : null}
          <AskGravitreSummonButton
            className="ov-btn"
            selected={{ kind: "approval", id: a.id, label: a.title }}
            label="Ask Gravitre about this"
          />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button type="button" className="ov-btn" aria-label="More actions">
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
        </div>
        <span className="ov-keys">
          <span className="ov-kbd">J</span>
          <span className="ov-kbd">K</span>move
          {pending ? (
            <>
              <span className="ov-kbd">A</span>approve <span className="ov-kbd">R</span>Reject with a reason
            </>
          ) : null}
        </span>
      </div>
    </article>
  )
}

/** The three risk paths, each with how many requests in the loaded queue took it. */
function RiskLadder({ pending, history }: { pending: Approval[]; history: Approval[] | null }) {
  const all = [...pending, ...(history ?? [])]
  const count = (level: RiskLevel) => all.filter((a) => a.context.riskLevel === level).length
  const rungs: Array<{ level: RiskLevel; chip: string; title: string; body: string }> = [
    {
      level: "low",
      chip: "Low risk",
      title: "Runs on its own",
      body: "Read only lookups and drafts. Logged in Activity, no approval needed.",
    },
    {
      level: "medium",
      chip: "Medium risk",
      title: "One approval",
      body: "Writes to one system, like updating a CRM record or posting to Slack.",
    },
    {
      level: "high",
      chip: "High risk",
      title: "Two approvals and an SLA",
      body: "Money, customer email or deletes. Escalates if no one decides in time.",
    },
  ]
  return (
    <section aria-labelledby="policy-heading" className="ov-explain">
      <div className="ov-explain-side">
        <span className="ov-sq-row">
          <span className="ov-sq" aria-hidden />
          <h2 id="policy-heading">How risk decides who approves</h2>
        </span>
        <p>
          Each action is scored before it runs. The score picks the path, so routine work keeps moving and anything
          that can hurt waits for a person.
        </p>
        <Link href={POLICIES_HREF}>Edit approval policies</Link>
      </div>
      <div className="ov-explain-main">
        {rungs.map((r) => (
          <div className="ov-riskcard" key={r.level}>
            <span className={cn("ov-chip", RISK_TONE[r.level])}>{r.chip}</span>
            <b>{r.title}</b>
            <p>{r.body}</p>
            {history ? (
              <span className="live">
                {count(r.level)} in this queue
              </span>
            ) : null}
            <span className={cn("ov-meter", RISK_TONE[r.level])} aria-hidden>
              <i />
              <i />
              <i />
            </span>
          </div>
        ))}
      </div>
    </section>
  )
}
