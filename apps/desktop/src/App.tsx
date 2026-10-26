import { useCallback, useEffect, useState } from "react"
import { StoreProvider, useStore, type Toast, type View } from "./store"
import { clearPendingSignIn, loadPendingSignIn, loadSession, parseAuthDeepLink, saveSession, type DesktopSession } from "./lib/session"
import { desktopRelease, isNewer, openWeb, type DesktopRelease } from "./lib/api"
import { Avatar, Icon, MarkTile, WorkspaceTile, type IconName } from "./ui"
import { CommandBar, Notices, QuickAsk, UserMenu, VIEW_KEYS, WorkspaceMenu } from "./Overlays"
import { SignIn, SignedIn, Unsupported } from "./views/SignIn"
import { Home } from "./views/Home"
import { Ask } from "./views/Ask"
import { Voice } from "./views/Voice"
import { Assignments } from "./views/Assignments"
import { Approvals } from "./views/Approvals"
import { Activity } from "./views/Activity"
import { Settings, useAppVersion } from "./views/Settings"

const NAV: [View, string, IconName][] = [
  ["home", "Home", "home"],
  ["ask", "Ask", "ask"],
  ["assign", "Assignments", "assign"],
  ["appr", "Approvals", "appr"],
  ["act", "Activity", "act"],
  ["voice", "Voice", "voice"],
]

/** Ask and Voice give the thread room: the rail collapses to icons. */
const COMPACT: View[] = ["ask", "voice"]

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

/** Release info from gravitre.app/desktop/latest.json, the file /download reads. */
function useRelease(): { version: string | null; release: DesktopRelease | null } {
  const version = useAppVersion()
  const [release, setRelease] = useState<DesktopRelease | null>(null)
  useEffect(() => {
    let alive = true
    const load = () => void desktopRelease().then((r) => alive && r && setRelease(r))
    load()
    const t = window.setInterval(load, 6 * 3600_000)
    return () => {
      alive = false
      window.clearInterval(t)
    }
  }, [])
  return { version, release }
}

function UpdateBanner({ latest, notes }: { latest: string; notes: string | null }) {
  const { web } = useStore()
  const [dismissed, setDismissed] = useState(false)
  if (dismissed) return null
  return (
    <div className="banner" role="status">
      <Icon name="download" style={{ color: "var(--sig)" }} />
      <span style={{ fontSize: 13, flex: 1 }}>
        <b>Gravitre {latest} is ready.</b> Download it to update. It takes a few seconds and your work stays put.
      </span>
      {notes ? (
        <button className="btn btn-q btn-sm" onClick={() => web(notes)}>
          What's new ↗
        </button>
      ) : null}
      <button className="btn btn-p btn-sm" onClick={() => web("/download")}>
        Download update
      </button>
      <button className="ib" aria-label="Dismiss" onClick={() => setDismissed(true)}>
        <Icon name="x" />
      </button>
    </div>
  )
}

function ToastView({ t, i }: { t: Toast; i: number }) {
  const [, tick] = useState(0)
  useEffect(() => {
    if (!t.undo) return
    const id = window.setInterval(() => tick((n) => n + 1), 250)
    return () => window.clearInterval(id)
  }, [t.undo])
  const left = t.undo ? Math.max(0, Math.ceil((t.undo.until - Date.now()) / 1000)) : 0
  return (
    <div className="toast fade" role="status" style={{ bottom: 76 + i * 50 }}>
      <Icon name={t.tone === "error" ? "alert" : "check"} style={{ color: t.tone === "error" ? "#ec9a9a" : "#19c37d" }} />
      <span>{t.text}</span>
      {t.undo ? (
        <button className="tbtn" onClick={t.undo.cancel}>
          Undo · {left}s
        </button>
      ) : (
        <span style={{ width: 8 }} />
      )}
    </div>
  )
}

function Rail() {
  const { nav, go, setOverlay, me, session, approvals, web, synced } = useStore()
  const view = nav.view
  const ws = me?.organizations.find((o) => o.id === session.orgId)
  const wsName = ws?.name || "Workspace"
  const n = approvals.data.length
  const syncLabel = synced.offline ? "Offline" : synced.at ? "Synced" : "Connecting…"
  const syncDot = synced.offline ? "var(--ap)" : synced.at ? "var(--ok)" : "var(--bx)"

  if (COMPACT.includes(view)) {
    return (
      <nav className="crail" aria-label="Main">
        <span style={{ height: 6 }} />
        <MarkTile size={24} />
        <span style={{ height: 14 }} />
        {NAV.map(([v, label, icon]) => (
          <button key={v} className={`cn ${view === v ? "on" : ""}`} aria-current={view === v ? "page" : undefined} aria-label={label} title={label} onClick={() => go(v)}>
            <Icon name={icon} />
            {v === "appr" && n ? <span className="badge">{n}</span> : null}
          </button>
        ))}
        <span style={{ flex: 1 }} />
        <span className="dot" title={syncLabel} aria-label={syncLabel} style={{ background: syncDot, marginBottom: 10 }} />
        <button className="cn" onClick={() => setOverlay("ws")} aria-label={`Switch workspace, current ${wsName}`} title={wsName}>
          <WorkspaceTile name={wsName} size={24} />
        </button>
        <button className={`cn ${view === "settings" ? "on" : ""}`} onClick={() => setOverlay("user")} aria-label="Account menu" title={me?.name || "Account"}>
          <Avatar name={me?.name || "You"} size={24} color="var(--carbon)" />
        </button>
      </nav>
    )
  }

  return (
    <nav className="rail" aria-label="Main">
      <div className="brand">
        <MarkTile size={24} />
        <span style={{ fontWeight: 600, fontSize: 15 }}>Gravitre</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {NAV.map(([v, label, icon]) => (
          <button key={v} className={`nv ${view === v ? "on" : ""}`} aria-current={view === v ? "page" : undefined} onClick={() => go(v)}>
            <Icon name={icon} />
            <span style={{ flex: 1 }}>{label}</span>
            {v === "appr" && n ? <span className="count">{n}</span> : null}
          </button>
        ))}
      </div>
      <div style={{ height: 1, background: "var(--bd)", margin: "10px 4px" }} />
      <button className="nv" onClick={() => web("/home")}>
        <Icon name="ext" />
        <span>Open Gravitre</span>
      </button>
      <span style={{ flex: 1 }} />
      <div title={synced.at ? `Synced ${new Date(synced.at).toLocaleTimeString()}` : syncLabel} style={{ display: "flex", alignItems: "center", gap: 6, padding: "0 10px 8px", fontSize: 12, color: "var(--t3)" }}>
        <span className="dot" style={{ background: syncDot }} />
        {syncLabel}
      </div>
      <button className="wsbox" onClick={() => setOverlay("ws")} aria-label={`Switch workspace, current ${wsName}`}>
        <WorkspaceTile name={wsName} />
        <span className="ell" style={{ flex: 1, textAlign: "left", fontSize: 13, fontWeight: 600 }}>
          {wsName}
        </span>
        <Icon name="chevrons" size={14} style={{ color: "var(--t3)" }} />
      </button>
      <button className={`mebtn ${view === "settings" ? "on" : ""}`} onClick={() => setOverlay("user")} aria-label="Account menu">
        <Avatar name={me?.name || "You"} size={24} color="var(--carbon)" />
        <span className="ell" style={{ flex: 1, fontSize: 13 }}>
          {view === "settings" ? "Settings" : me?.name || "Account"}
        </span>
      </button>
    </nav>
  )
}

function Shell({ welcome, onWelcomeDone }: { welcome: boolean; onWelcomeDone: () => void }) {
  const store = useStore()
  const { nav, go, overlay, setOverlay, setPrefs, session, toasts } = store
  useExternalLinks(session.appBase)
  const { version, release } = useRelease()

  // Shortcuts and tray items from the operating system arrive as Tauri events.
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
        await add("pause-notifications", () => {
          setPrefs({ pausedUntil: Date.now() + 3600_000 })
          store.toast("Notifications paused for 1 hour. Failures still show.")
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

  if (version && release?.minimum && isNewer(release.minimum, version)) {
    return <Unsupported release={release} />
  }
  if (welcome) return <SignedIn onDone={onWelcomeDone} />

  const view = nav.view
  const newer = version && release && isNewer(release.version, version) ? release : null
  return (
    <div className="shell">
      <div className="body">
        <Rail />
        <main className="main">
          {newer ? <UpdateBanner latest={newer.version} notes={newer.notes} /> : null}
          <div className="view" key={`${view}`}>
            {view === "home" ? <Home /> : null}
            {view === "ask" ? <Ask /> : null}
            {view === "voice" ? <Voice /> : null}
            {view === "assign" ? <Assignments /> : null}
            {view === "appr" ? <Approvals /> : null}
            {view === "act" ? <Activity /> : null}
            {view === "settings" ? <Settings release={release} /> : null}
          </div>
        </main>
      </div>
      {toasts.map((t, i) => (
        <ToastView key={t.id} t={t} i={i} />
      ))}
      <Notices />
      {overlay === "ws" ? <WorkspaceMenu /> : null}
      {overlay === "user" ? <UserMenu /> : null}
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

function Themed({ children }: { children: React.ReactNode }) {
  const { dark } = useStore()
  return <div className={`g ${dark ? "dark" : ""}`}>{children}</div>
}

export default function App() {
  const [session, setSession] = useState<DesktopSession | null>(() => loadSession())
  const [notice, setNotice] = useState<string | null>(null)
  const [welcome, setWelcome] = useState(false)
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
        if (!expected || expected.expired || link.code !== expected.code) {
          setNotice("That sign-in link doesn't match this computer's code. Start again from here.")
          continue
        }
        clearPendingSignIn()
        saveSession(link.session)
        setNotice(null)
        setWelcome(true)
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
      <Themed>
        <Shell welcome={welcome} onWelcomeDone={() => setWelcome(false)} />
      </Themed>
    </StoreProvider>
  )
}
