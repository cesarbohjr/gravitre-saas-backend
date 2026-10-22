import { useCallback, useEffect, useState } from "react"
import { StoreProvider, useStore, type View } from "./store"
import { clearPendingSignIn, loadPendingSignIn, loadSession, parseAuthDeepLink, saveSession, type DesktopSession } from "./lib/session"
import { isNewer, latestDesktopRelease, openWeb } from "./lib/api"
import { Avatar, Icon, Mark, MOD, SHIFT, type IconName } from "./ui"
import { CommandBar, Notifications, QuickAsk, UserMenu, VIEW_KEYS, WorkspaceMenu } from "./Overlays"
import { SignIn } from "./views/SignIn"
import { Home } from "./views/Home"
import { Ask } from "./views/Ask"
import { Voice } from "./views/Voice"
import { Assignments } from "./views/Assignments"
import { Approvals } from "./views/Approvals"
import { Activity } from "./views/Activity"
import { Settings, useAppVersion } from "./views/Settings"

const NAV: (null | [View, string, IconName])[] = [
  ["home", "Home", "home"],
  ["ask", "Ask", "ask"],
  ["voice", "Voice", "voice"],
  null,
  ["assign", "Assignments", "assign"],
  ["appr", "Approvals", "appr"],
  ["act", "Activity", "act"],
]

/** Links inside answers and pages open in the default browser, never inside the app window. */
function useExternalLinks(appBase: string) {
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      const a = (e.target as HTMLElement | null)?.closest?.("a")
      const href = a?.getAttribute("href")
      if (!a || !href || !/^https?:\/\//.test(href)) return
      e.preventDefault()
      void openWeb(appBase, href)
    }
    document.addEventListener("click", onClick)
    return () => document.removeEventListener("click", onClick)
  }, [appBase])
}

function UpdateBanner() {
  const version = useAppVersion()
  const { web } = useStore()
  const [latest, setLatest] = useState<string | null>(null)
  const [dismissed, setDismissed] = useState(false)
  useEffect(() => {
    if (!version) return
    void latestDesktopRelease().then((r) => r && isNewer(r.version, version) && setLatest(r.version))
  }, [version])
  if (!latest || dismissed) return null
  return (
    <div role="status" style={{ display: "flex", alignItems: "center", gap: 12, minHeight: 44, padding: "0 10px 0 24px", background: "var(--sigs)", borderBottom: "1px solid var(--bd)" }}>
      <Icon name="download" style={{ color: "var(--sig)" }} />
      <span style={{ fontSize: 13, flex: 1 }}>
        <b>Gravitre {latest} is out.</b> Download it to update. Your work stays put.
      </span>
      <button className="btn btn-k btn-sm" onClick={() => web("/download")}>
        Download update
      </button>
      <button className="ib" aria-label="Dismiss" onClick={() => setDismissed(true)}>
        <Icon name="x" />
      </button>
    </div>
  )
}

function Shell() {
  const store = useStore()
  const { nav, go, overlay, setOverlay, prefs, setPrefs, dark, me, session, approvals, assignments, toasts, web } = store
  useExternalLinks(session.appBase)
  const wide = prefs.railWide
  const pending = approvals.data.length + assignments.data.filter((a) => a.status === "waiting").length
  const ws = me?.organizations.find((o) => o.id === session.orgId)

  // Shortcuts from the operating system (tray, global shortcuts) arrive as Tauri events.
  useEffect(() => {
    const off: (() => void)[] = []
    let alive = true
    void import("@tauri-apps/api/event")
      .then(async ({ listen }) => {
        const add = async (name: string, fn: (payload: unknown) => void) => {
          const un = await listen(name, (e) => fn(e.payload))
          if (alive) off.push(un)
          else un()
        }
        await add("quick-ask", () => setOverlay("quick"))
        await add("push-to-talk", () => {
          if (store.nav.view === "voice") window.dispatchEvent(new Event("gravitre:ptt"))
          else go({ view: "voice", listen: true })
        })
        await add("open-view", (payload) => {
          const v = String(payload) as View
          if (["home", "ask", "voice", "assign", "appr", "act", "settings"].includes(v)) go(v)
        })
      })
      .catch(() => {})
    return () => {
      alive = false
      off.forEach((f) => f())
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [store.nav.view])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey
      if (e.key === "Escape" && overlay) {
        setOverlay(null)
        return
      }
      if (!mod) return
      const k = e.key.toLowerCase()
      if (k === "k") (e.preventDefault(), setOverlay(overlay === "cmd" ? null : "cmd"))
      else if (k === ",") (e.preventDefault(), go("settings"))
      else if (k === "n") (e.preventDefault(), go({ view: "ask", select: null }))
      else if (e.shiftKey && e.code === "Space") (e.preventDefault(), setOverlay("quick"))
      else {
        const hit = VIEW_KEYS.find(([, , , n]) => n === e.key)
        if (hit) (e.preventDefault(), go(hit[0]))
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [go, overlay, setOverlay])

  const view = nav.view
  return (
    <div className={`g ${dark ? "dark" : ""}`}>
      <div className="shell">
        <div className="body">
          <nav className={`rail ${wide ? "" : "mini"}`} aria-label="Main">
            <div style={{ height: 12, flex: "none" }} />
            <button className="wsbtn" onClick={() => setOverlay("ws")} aria-label={`Switch workspace, current ${ws?.name || "workspace"}`}>
              <Mark />
              <span className="lbl" style={{ flex: 1, textAlign: "left", display: "flex", flexDirection: "column", lineHeight: 1.2, minWidth: 0 }}>
                <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{ws?.name || "Gravitre"}</span>
                <span style={{ fontSize: 11, fontWeight: 400, color: "var(--t3)", display: "inline-flex", alignItems: "center", gap: 5 }}>
                  <span className="dot" style={{ background: approvals.error ? "var(--ap)" : approvals.at ? "var(--ok)" : "var(--bx)" }} />
                  {approvals.error ? "Reconnecting" : approvals.at ? "Synced" : "Connecting"}
                </span>
              </span>
              <span className="lbl" style={{ flex: "none", display: "inline-flex" }}>
                <Icon name="chevrons" style={{ color: "var(--t3)" }} />
              </span>
            </button>
            <span className="rsep" />
            {NAV.map((n, i) =>
              n ? (
                <button key={n[0]} className={`rn ${view === n[0] ? "on" : ""}`} aria-current={view === n[0] ? "page" : undefined} aria-label={n[1]} title={n[1]} onClick={() => go(n[0])}>
                  <Icon name={n[2]} />
                  <span className="lbl">{n[1]}</span>
                  {n[0] === "appr" && approvals.data.length ? (
                    <span className="rdot" style={{ background: "#e2a33a" }}>
                      {approvals.data.length}
                    </span>
                  ) : null}
                </button>
              ) : (
                <span key={`s${i}`} className="rhead">
                  Work
                </span>
              ),
            )}
            <span style={{ flex: 1 }} />
            <button className="rn" aria-label="Open Gravitre on the web" title="Open Gravitre on the web" onClick={() => web("/home")}>
              <Icon name="ext" />
              <span className="lbl">Open on web</span>
            </button>
            <button className={`rn ${view === "settings" ? "on" : ""}`} aria-label="Settings" title="Settings" onClick={() => go("settings")}>
              <Icon name="settings" />
              <span className="lbl">Settings</span>
            </button>
            <span className="rsep" />
            <button className="rn" onClick={() => setOverlay("user")} aria-label="Account menu">
              <Avatar name={me?.name || "You"} size={24} color="#2b59e0" />
              <span className="lbl" style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {me?.name || "Account"}
              </span>
            </button>
          </nav>
          <div className="col">
            <header className="top">
              <button className="tb" aria-label={wide ? "Collapse sidebar" : "Show sidebar"} title={wide ? "Collapse sidebar" : "Show sidebar"} onClick={() => setPrefs({ railWide: !wide })}>
                <Icon name="rail" />
              </button>
              <span style={{ flex: 1 }} />
              <button className="search" onClick={() => setOverlay("cmd")}>
                <Icon name="search" />
                <span style={{ flex: 1, textAlign: "left" }}>Search or command…</span>
                <span className="k">{MOD}K</span>
              </button>
              <span style={{ flex: 1 }} />
              <button className="btn btn-sm" onClick={() => setOverlay("quick")} title={`Quick Ask ${MOD}${SHIFT}Space`}>
                <Icon name="ask" size={14} style={{ color: "var(--br)" }} />
                Quick Ask
              </button>
              <button className="tb" aria-label="Notifications" onClick={() => setOverlay("notif")}>
                <Icon name="bell" />
                {pending ? <span style={{ position: "absolute", top: 6, right: 6, width: 8, height: 8, borderRadius: "50%", background: "#e2a33a", boxShadow: "0 0 0 2px var(--cv)" }} /> : null}
              </button>
            </header>
            <main className="main">
              <UpdateBanner />
              {view === "home" ? <Home /> : null}
              {view === "ask" ? <Ask /> : null}
              {view === "voice" ? <Voice /> : null}
              {view === "assign" ? <Assignments /> : null}
              {view === "appr" ? <Approvals /> : null}
              {view === "act" ? <Activity /> : null}
              {view === "settings" ? <Settings /> : null}
            </main>
          </div>
        </div>
      </div>
      {toasts.map((t, i) => (
        <div key={t.id} className="toast fade" role="status" style={{ bottom: 28 + i * 52 }}>
          <Icon name={t.tone === "error" ? "alert" : "check"} style={{ color: t.tone === "error" ? "#ec9a9a" : "#19c37d" }} />
          <span>{t.text}</span>
        </div>
      ))}
      {overlay === "ws" ? <WorkspaceMenu /> : null}
      {overlay === "user" ? <UserMenu /> : null}
      {overlay === "notif" ? <Notifications /> : null}
      {overlay === "cmd" ? <CommandBar /> : null}
      {overlay === "quick" ? <QuickAsk /> : null}
    </div>
  )
}

function useSystemDark(): boolean {
  const [dark, setDark] = useState(() => window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false)
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)")
    if (!mq) return
    const on = (e: MediaQueryListEvent) => setDark(e.matches)
    mq.addEventListener("change", on)
    return () => mq.removeEventListener("change", on)
  }, [])
  return dark
}

export default function App() {
  const [session, setSession] = useState<DesktopSession | null>(() => loadSession())
  const [notice, setNotice] = useState<string | null>(null)
  const systemDark = useSystemDark()

  const onSession = useCallback((next: DesktopSession | null) => {
    setSession((prev) => {
      if (!next && prev) setNotice("You're signed out of this computer.")
      return next
    })
  }, [])

  // gravitre://auth links come from /desktop/connect; only the sign-in started here is accepted.
  useEffect(() => {
    const handle = (urls: string[]) => {
      for (const url of urls) {
        const link = parseAuthDeepLink(url)
        if (!link) continue
        const expected = loadPendingSignIn()
        if (!expected || link.code !== expected) {
          setNotice("That sign-in link doesn't match this computer's code. Start again from here.")
          continue
        }
        clearPendingSignIn()
        saveSession(link.session)
        setNotice(null)
        setSession(link.session)
      }
    }
    let off: (() => void) | null = null
    let alive = true
    void import("@tauri-apps/plugin-deep-link")
      .then(async ({ onOpenUrl, getCurrent }) => {
        const started = await getCurrent().catch(() => null)
        if (started?.length) handle(started)
        const un = await onOpenUrl(handle)
        if (alive) off = un
        else un()
      })
      .catch(() => {})
    return () => {
      alive = false
      off?.()
    }
  }, [])

  if (!session) {
    return (
      <div className={`g ${systemDark ? "dark" : ""}`}>
        <SignIn notice={notice} />
      </div>
    )
  }
  return (
    <StoreProvider session={session} onSession={onSession}>
      <Shell />
    </StoreProvider>
  )
}
