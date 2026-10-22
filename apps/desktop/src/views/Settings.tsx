import { useEffect, useState, type ReactNode } from "react"
import { useStore } from "../store"
import { ALT, Icon, MOD, PageHead, SHIFT, Toggle } from "../ui"
import { isNewer, latestDesktopRelease } from "../lib/api"
import type { Prefs, ThemePick } from "../lib/prefs"

const WEB_LINKS: { label: string; path: string }[] = [
  { label: "Account and sign-in", path: "/settings/profile" },
  { label: "Workspace and team", path: "/settings" },
  { label: "Agents, Plays and Workflows", path: "/agents" },
  { label: "Connectors and sources", path: "/connectors" },
  { label: "Trust & Safety", path: "/trust-safety" },
]

async function autostart() {
  try {
    return await import("@tauri-apps/plugin-autostart")
  } catch {
    return null
  }
}

export function useAppVersion(): string | null {
  const [version, setVersion] = useState<string | null>(null)
  useEffect(() => {
    import("@tauri-apps/api/app")
      .then((m) => m.getVersion())
      .then(setVersion)
      .catch(() => setVersion(null))
  }, [])
  return version
}

function Row({ title, sub, first, children }: { title: string; sub?: string; first?: boolean; children: ReactNode }) {
  return (
    <div className={`srow ${first ? "first" : ""}`}>
      <span style={{ flex: 1, display: "flex", flexDirection: "column", lineHeight: 1.35 }}>
        <span style={{ fontWeight: 500 }}>{title}</span>
        {sub ? <span className="sub">{sub}</span> : null}
      </span>
      {children}
    </div>
  )
}

export function Settings() {
  const { prefs, setPrefs, web, toast } = useStore()
  const version = useAppVersion()
  const [login, setLogin] = useState<boolean | null>(null)
  const [mics, setMics] = useState<MediaDeviceInfo[]>([])
  const [upd, setUpd] = useState<string>("")

  useEffect(() => {
    void autostart().then(async (m) => {
      if (!m) return
      try {
        setLogin(await m.isEnabled())
      } catch {
        setLogin(null)
      }
    })
    navigator.mediaDevices
      ?.enumerateDevices()
      .then((all) => setMics(all.filter((d) => d.kind === "audioinput")))
      .catch(() => setMics([]))
  }, [])

  const setLoginAtStartup = async (next: boolean) => {
    const m = await autostart()
    if (!m) return
    try {
      if (next) await m.enable()
      else await m.disable()
      setLogin(await m.isEnabled())
    } catch {
      toast("Couldn't change that setting on this computer.", "error")
    }
  }

  const checkUpdates = async () => {
    setUpd("Checking…")
    const latest = await latestDesktopRelease()
    if (!latest) return setUpd("Couldn't check right now")
    if (version && isNewer(latest.version, version)) {
      setUpd(`Version ${latest.version} is available`)
      web("/download")
    } else setUpd("Up to date · checked just now")
  }

  const notif: { key: keyof Prefs; title: string; sub: string }[] = [
    { key: "notifyApprovals", title: "Approval needed", sub: "The moment an agent pauses for you" },
    { key: "notifyDone", title: "Assignment finished", sub: "With the outcome in one line" },
    { key: "notifyFailed", title: "Run failed", sub: "Says what stopped it" },
    { key: "quietHours", title: "Quiet hours", sub: "6:00 PM to 8:00 AM on weekdays, and weekends. Failures still show." },
  ]

  return (
    <div className="page fade">
      <PageHead eyebrow="This computer" title="Settings" lede="Settings here apply to this device only. Account, workspace, agents and policies live on the web." />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(420px, 100%), 1fr))", gap: 16, alignItems: "start" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <section className="card" style={{ overflow: "hidden" }}>
            <div className="band" style={{ padding: "14px 20px" }}>
              <span style={{ fontSize: 15, fontWeight: 600 }}>General</span>
            </div>
            {login !== null ? (
              <Row first title="Open at login" sub="Start Gravitre when you sign in to this computer">
                <Toggle on={login} label="Open at login" onChange={(v) => void setLoginAtStartup(v)} />
              </Row>
            ) : null}
            <div className={`srow ${login === null ? "first" : ""}`}>
              <span style={{ flex: 1, fontWeight: 500 }}>Theme</span>
              <div className="tabs" role="radiogroup" aria-label="Theme">
                {(["light", "dark", "system"] as ThemePick[]).map((t) => (
                  <button key={t} className={prefs.theme === t ? "on" : ""} role="radio" aria-checked={prefs.theme === t} onClick={() => setPrefs({ theme: t })} style={{ height: 30 }}>
                    {t === "light" ? "Light" : t === "dark" ? "Dark" : "System"}
                  </button>
                ))}
              </div>
            </div>
          </section>
          <section className="card" style={{ overflow: "hidden" }}>
            <div className="band" style={{ padding: "14px 20px" }}>
              <span style={{ fontSize: 15, fontWeight: 600 }}>Notifications</span>
            </div>
            {notif.map((n, i) => (
              <Row key={n.key} first={i === 0} title={n.title} sub={n.sub}>
                <Toggle on={Boolean(prefs[n.key])} label={n.title} onChange={(v) => setPrefs({ [n.key]: v } as Partial<Prefs>)} />
              </Row>
            ))}
          </section>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <section className="card" style={{ overflow: "hidden" }}>
            <div className="band" style={{ padding: "14px 20px" }}>
              <span style={{ fontSize: 15, fontWeight: 600 }}>Shortcuts</span>
            </div>
            <Row first title="Quick Ask" sub="Works from any app">
              <span className="kbd" style={{ fontSize: 12 }}>
                {MOD} {SHIFT} Space
              </span>
            </Row>
            <Row title="Talk" sub="Press to start talking from any app, press again to send">
              <span className="kbd" style={{ fontSize: 12 }}>
                {ALT} Space
              </span>
            </Row>
            <Row title="Command bar">
              <span className="kbd" style={{ fontSize: 12 }}>
                {MOD} K
              </span>
            </Row>
          </section>
          <section className="card" style={{ overflow: "hidden" }}>
            <div className="band" style={{ padding: "14px 20px" }}>
              <span style={{ fontSize: 15, fontWeight: 600 }}>Microphone and updates</span>
            </div>
            <div className="srow first">
              <label htmlFor="mic" style={{ flex: 1, fontWeight: 500 }}>
                Microphone
              </label>
              <select id="mic" className="select" value={prefs.micId} onChange={(e) => setPrefs({ micId: e.target.value })}>
                <option value="">System default</option>
                {mics
                  .filter((m) => m.deviceId && m.deviceId !== "default")
                  .map((m, i) => (
                    <option key={m.deviceId} value={m.deviceId}>
                      {m.label || `Microphone ${i + 1}`}
                    </option>
                  ))}
              </select>
            </div>
            <Row title={version ? `Version ${version}` : "Version"} sub={upd || "Gravitre tells you when a new version is out"}>
              <button className="btn btn-sm" onClick={() => void checkUpdates()}>
                Check for updates
              </button>
            </Row>
          </section>
          <section className="card" style={{ overflow: "hidden" }}>
            <div className="band" style={{ padding: "14px 20px" }}>
              <span style={{ fontSize: 15, fontWeight: 600 }}>Manage on web</span>
            </div>
            {WEB_LINKS.map((w, i) => (
              <button key={w.label} className={`srow linkrow ${i === 0 ? "first" : ""}`} onClick={() => web(w.path)} style={{ minHeight: 46 }}>
                <span style={{ flex: 1, textAlign: "left" }}>{w.label}</span>
                <Icon name="ext" style={{ color: "var(--t3)" }} />
              </button>
            ))}
          </section>
        </div>
      </div>
    </div>
  )
}
