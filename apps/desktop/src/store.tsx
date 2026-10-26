import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import type { Approval } from "@web/components/approvals/decision-queue/model"
import { createApi, openWeb, SignedOutError, type ActivityEvent, type Agent, type Api, type Me } from "./lib/api"
import { toAssignment, type Assignment } from "./lib/model"
import { loadPrefs, notificationsHeld, savePrefs, type Prefs } from "./lib/prefs"
import { clearSession, saveSession, type DesktopSession } from "./lib/session"

export type View = "home" | "ask" | "voice" | "assign" | "appr" | "act" | "settings"
export type Overlay = null | "ws" | "user" | "cmd" | "quick"

export type Nav = {
  view: View
  /** Selected item on the target view (approval id, assignment id, activity id, conversation id). */
  select?: string | null
  /** Text to send as soon as Ask opens (home ask bar, chips, command bar). */
  ask?: string | null
  /** Voice view starts listening right away (push-to-talk shortcut). */
  listen?: boolean
}

export type Toast = {
  id: number
  text: string
  tone: "ok" | "error"
  /** Undo window: the action runs when it closes unless Undo is pressed. */
  undo?: { until: number; cancel: () => void }
}

export type Notice = { id: number; title: string; body: string; time: string; open: Nav; approval?: Approval }

type Feed<T> = { data: T; at: number | null; error: string | null }

const empty = <T,>(data: T): Feed<T> => ({ data, at: null, error: null })

type Store = {
  api: Api
  session: DesktopSession
  me: Me | null
  prefs: Prefs
  setPrefs: (patch: Partial<Prefs>) => void
  dark: boolean
  nav: Nav
  go: (next: Nav | View) => void
  overlay: Overlay
  setOverlay: (o: Overlay) => void
  approvals: Feed<Approval[]>
  history: Feed<Approval[]>
  assignments: Feed<Assignment[]>
  activity: Feed<ActivityEvent[]>
  totals: Feed<{ hoursSaved: number | null; completed: number | null }>
  agents: Agent[]
  refresh: (which?: "approvals" | "assignments" | "activity" | "all") => Promise<void>
  toast: (text: string, tone?: "ok" | "error") => void
  toasts: Toast[]
  /** Approves after a 4 second undo window; the item leaves the queue at once. */
  approveWithUndo: (a: Approval) => void
  notices: Notice[]
  dismissNotice: (id: number) => void
  /** Approval ids approved but still inside their undo window. */
  holding: Set<string>
  /** The signed-in role's capabilities; null until known or when the workspace didn't say. */
  caps: string[] | null
  canApprove: boolean
  /** Last successful sync, or null while offline / never loaded. */
  synced: { at: number | null; offline: boolean }
  web: (path?: string) => void
  switchWorkspace: (orgId: string) => void
  signOut: () => void
}

const Ctx = createContext<Store | null>(null)

export function useStore(): Store {
  const value = useContext(Ctx)
  if (!value) throw new Error("useStore outside StoreProvider")
  return value
}

function message(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback
}

async function nativeNotify(title: string, body: string) {
  try {
    const n = await import("@tauri-apps/plugin-notification")
    let granted = await n.isPermissionGranted()
    if (!granted) granted = (await n.requestPermission()) === "granted"
    if (granted) n.sendNotification({ title, body })
  } catch {
    /* browser preview */
  }
}

export function StoreProvider({
  session,
  onSession,
  children,
}: {
  session: DesktopSession
  onSession: (next: DesktopSession | null) => void
  children: ReactNode
}) {
  const sessionRef = useRef(session)
  sessionRef.current = session
  const api = useMemo(
    () =>
      createApi({
        get: () => sessionRef.current,
        set: (next) => {
          if (next) {
            saveSession(next)
            sessionRef.current = next
          } else clearSession()
          onSession(next)
        },
      }),
    [onSession],
  )

  const [prefs, setPrefsState] = useState<Prefs>(loadPrefs)
  const setPrefs = useCallback((patch: Partial<Prefs>) => {
    setPrefsState((prev) => {
      const next = { ...prev, ...patch }
      savePrefs(next)
      return next
    })
  }, [])
  const [systemDark, setSystemDark] = useState(() => window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false)
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)")
    if (!mq) return
    const on = (e: MediaQueryListEvent) => setSystemDark(e.matches)
    mq.addEventListener("change", on)
    return () => mq.removeEventListener("change", on)
  }, [])
  const dark = prefs.theme === "dark" || (prefs.theme === "system" && systemDark)

  const [nav, setNav] = useState<Nav>({ view: "home" })
  const [overlay, setOverlay] = useState<Overlay>(null)
  const go = useCallback((next: Nav | View) => {
    setNav(typeof next === "string" ? { view: next } : next)
    setOverlay(null)
  }, [])

  const [toasts, setToasts] = useState<Toast[]>([])
  const toast = useCallback((text: string, tone: "ok" | "error" = "ok") => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t.slice(-2), { id, text, tone }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200)
  }, [])
  const [holding, setHolding] = useState<Set<string>>(() => new Set())
  const [notices, setNotices] = useState<Notice[]>([])
  const dismissNotice = useCallback((id: number) => setNotices((n) => n.filter((x) => x.id !== id)), [])
  /** Native notification when Gravitre is in the background; an in-app card (with its buttons) when it is in front. */
  const notify = useCallback((n: Omit<Notice, "id" | "time">) => {
    if (document.visibilityState === "visible" && document.hasFocus()) {
      const id = Date.now() + Math.random()
      const time = new Date().toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
      setNotices((prev) => [...prev.slice(-2), { ...n, id, time }])
      window.setTimeout(() => setNotices((prev) => prev.filter((x) => x.id !== id)), 12_000)
    } else void nativeNotify(n.title, n.body)
  }, [])
  const [caps, setCaps] = useState<string[] | null>(null)
  const [offline, setOffline] = useState(() => typeof navigator !== "undefined" && navigator.onLine === false)

  const [me, setMe] = useState<Me | null>(null)
  const [approvals, setApprovals] = useState<Feed<Approval[]>>(empty([]))
  const [history, setHistory] = useState<Feed<Approval[]>>(empty([]))
  const [assignments, setAssignments] = useState<Feed<Assignment[]>>(empty([]))
  const [activity, setActivity] = useState<Feed<ActivityEvent[]>>(empty([]))
  const [totals, setTotals] = useState<Feed<{ hoursSaved: number | null; completed: number | null }>>(
    empty({ hoursSaved: null, completed: null }),
  )
  const [agents, setAgents] = useState<Agent[]>([])

  // Notifications compare each poll with the previous one; the first load only sets the baseline.
  const seenApprovals = useRef<Set<string> | null>(null)
  const seenJobs = useRef<Map<string, string> | null>(null)
  const prefsRef = useRef(prefs)
  prefsRef.current = prefs

  const handleError = useCallback(
    (err: unknown) => {
      if (err instanceof SignedOutError) return true
      return false
    },
    [],
  )

  const loadApprovals = useCallback(async () => {
    try {
      const rows = await api.approvals()
      setApprovals({ data: rows, at: Date.now(), error: null })
      const ids = new Set(rows.map((a) => a.id))
      const seen = seenApprovals.current
      if (seen && prefsRef.current.notifyApprovals && !notificationsHeld(prefsRef.current)) {
        const fresh = rows.filter((a) => !seen.has(a.id))
        if (fresh.length === 1) {
          notify({ title: "Approval needed", body: `${fresh[0].title} · requested by ${fresh[0].requestedBy}`, open: { view: "appr", select: fresh[0].id }, approval: fresh[0] })
        } else if (fresh.length > 1) {
          notify({ title: "Approvals needed", body: `${fresh.length} new requests are waiting on you`, open: { view: "appr" } })
        }
      }
      seenApprovals.current = ids
    } catch (err) {
      if (!handleError(err)) setApprovals((f) => ({ ...f, error: message(err, "Couldn't load approvals") }))
    }
    api
      .approvalHistory()
      .then((rows) => setHistory({ data: rows, at: Date.now(), error: null }))
      .catch((err) => !handleError(err) && setHistory((f) => ({ ...f, error: message(err, "Couldn't load past decisions") })))
  }, [api, handleError, notify])

  const loadAssignments = useCallback(async () => {
    try {
      const rows = (await api.jobs()).map(toAssignment)
      setAssignments({ data: rows, at: Date.now(), error: null })
      const seen = seenJobs.current
      if (seen) {
        const p = prefsRef.current
        for (const a of rows) {
          const before = seen.get(a.id)
          if (!before || before === a.status) continue
          if (a.status === "done" && p.notifyDone && !notificationsHeld(p)) {
            notify({ title: "Assignment finished", body: a.outcome && a.outcome !== "Finished." ? `${a.title} · ${a.outcome.slice(0, 120)}` : a.title, open: { view: "assign", select: a.id } })
          }
          // Failures still show during quiet hours.
          if (a.status === "failed" && p.notifyFailed) {
            notify({ title: `Run failed: ${a.title}`, body: a.outcome || "Open Gravitre to see why.", open: { view: "assign", select: a.id } })
          }
          if (a.status === "waiting" && p.notifyApprovals && !notificationsHeld(p)) {
            notify({ title: "Approval needed", body: `${a.title} · ${a.agent}`, open: { view: "assign", select: a.id } })
          }
        }
      }
      seenJobs.current = new Map(rows.map((a) => [a.id, a.status]))
    } catch (err) {
      if (!handleError(err)) setAssignments((f) => ({ ...f, error: message(err, "Couldn't load assignments") }))
    }
  }, [api, handleError, notify])

  const loadActivity = useCallback(async () => {
    try {
      setActivity({ data: await api.activity(50), at: Date.now(), error: null })
    } catch (err) {
      if (!handleError(err)) setActivity((f) => ({ ...f, error: message(err, "Couldn't load activity") }))
    }
  }, [api, handleError])

  const loadTotals = useCallback(async () => {
    try {
      setTotals({ data: await api.weekTotals(), at: Date.now(), error: null })
    } catch (err) {
      if (!handleError(err)) setTotals((f) => ({ ...f, error: message(err, "Couldn't load results") }))
    }
  }, [api, handleError])

  const refresh = useCallback(
    async (which: "approvals" | "assignments" | "activity" | "all" = "all") => {
      const jobs: Promise<void>[] = []
      if (which === "approvals" || which === "all") jobs.push(loadApprovals())
      if (which === "assignments" || which === "all") jobs.push(loadAssignments())
      if (which === "activity" || which === "all") jobs.push(loadActivity())
      if (which === "all") jobs.push(loadTotals())
      await Promise.all(jobs)
    },
    [loadActivity, loadApprovals, loadAssignments, loadTotals],
  )

  // Workspace switches re-scope every request, so start every feed over.
  useEffect(() => {
    seenApprovals.current = null
    seenJobs.current = null
    setApprovals(empty([]))
    setHistory(empty([]))
    setAssignments(empty([]))
    setActivity(empty([]))
    setTotals(empty({ hoursSaved: null, completed: null }))
    api
      .me()
      .then(setMe)
      .catch((err) => !handleError(err) && toast(message(err, "Couldn't load your account"), "error"))
    api
      .agents()
      .then(setAgents)
      .catch(() => setAgents([]))
    setCaps(null)
    api
      .capabilities()
      .then((c) => setCaps(c ? c.capabilities : null))
      .catch(() => setCaps(null))
    void refresh("all")
    const fast = window.setInterval(() => {
      if (document.visibilityState === "visible" || prefsRef.current.notifyApprovals) {
        void loadApprovals()
        void loadAssignments()
      }
    }, 20_000)
    const slow = window.setInterval(() => {
      if (document.visibilityState === "visible") void loadActivity()
    }, 45_000)
    const totalsTimer = window.setInterval(() => void loadTotals(), 5 * 60_000)
    const onFocus = () => void refresh("all")
    window.addEventListener("focus", onFocus)
    return () => {
      window.clearInterval(fast)
      window.clearInterval(slow)
      window.clearInterval(totalsTimer)
      window.removeEventListener("focus", onFocus)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, session.orgId])

  const web = useCallback((path = "/") => void openWeb(sessionRef.current.appBase, path), [])

  useEffect(() => {
    const on = () => {
      setOffline(false)
      void refresh("all")
    }
    const off = () => setOffline(true)
    window.addEventListener("online", on)
    window.addEventListener("offline", off)
    return () => {
      window.removeEventListener("online", on)
      window.removeEventListener("offline", off)
    }
  }, [refresh])

  const approveWithUndo = useCallback(
    (a: Approval) => {
      const id = Date.now() + Math.random()
      let cancelled = false
      setHolding((h) => new Set(h).add(a.id))
      const release = () =>
        setHolding((h) => {
          const next = new Set(h)
          next.delete(a.id)
          return next
        })
      const cancel = () => {
        cancelled = true
        window.clearTimeout(timer)
        release()
        setToasts((t) => t.filter((x) => x.id !== id))
      }
      setToasts((t) => [...t.slice(-2), { id, text: `Approved: ${a.title}`, tone: "ok", undo: { until: Date.now() + 4000, cancel } }])
      const timer = window.setTimeout(async () => {
        setToasts((t) => t.filter((x) => x.id !== id))
        if (cancelled) return
        try {
          const result = await api.approve(a.id)
          if (result && result.success === false) toast(String(result.message ?? "Approved, but the action didn't run."), "error")
          else if (String(result?.status ?? "") === "pending_approval") toast("Recorded. Another approver is still needed.")
        } catch (err) {
          if (!(err instanceof SignedOutError)) toast(message(err, "That approval didn't go through"), "error")
        } finally {
          await loadApprovals()
          release()
        }
      }, 4000)
    },
    [api, loadApprovals, toast],
  )

  // Keep the tray menu's live rows in step with the app.
  const waitingN = approvals.data.filter((a) => !holding.has(a.id)).length
  const runningJob = assignments.data.find((a) => a.status === "running") || null
  useEffect(() => {
    void import("@tauri-apps/api/core")
      .then(({ invoke }) =>
        invoke("set_tray_status", {
          approvals: waitingN,
          running: runningJob ? runningJob.title.slice(0, 48) : null,
          progress: runningJob?.progress ?? null,
          visible: prefs.tray,
        }),
      )
      .catch(() => {})
  }, [waitingN, runningJob?.title, runningJob?.progress, prefs.tray, runningJob])

  const switchWorkspace = useCallback(
    (orgId: string) => {
      const next = { ...sessionRef.current, orgId }
      saveSession(next)
      onSession(next)
      setNav({ view: "home" })
      setOverlay(null)
    },
    [onSession],
  )

  const signOut = useCallback(() => {
    clearSession()
    onSession(null)
  }, [onSession])

  const value: Store = {
    api,
    session,
    me,
    prefs,
    setPrefs,
    dark,
    nav,
    go,
    overlay,
    setOverlay,
    // Approvals inside their undo window are already decided as far as the screens are concerned.
    approvals: holding.size ? { ...approvals, data: approvals.data.filter((a) => !holding.has(a.id)) } : approvals,
    history,
    assignments,
    activity,
    totals,
    agents,
    refresh,
    toast,
    toasts,
    approveWithUndo,
    notices,
    dismissNotice,
    holding,
    caps,
    canApprove: caps == null || caps.includes("approve_writes"),
    synced: { at: approvals.at, offline },
    web,
    switchWorkspace,
    signOut,
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
