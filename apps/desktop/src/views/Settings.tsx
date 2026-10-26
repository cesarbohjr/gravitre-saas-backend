import { useEffect, useRef, useState, type ReactNode } from "react"
import { useStore } from "../store"
import { ALT, Icon, MOD, SHIFT, Toggle } from "../ui"
import { desktopRelease, isNewer, type DesktopRelease } from "../lib/api"
import { hourLabel, type Prefs, type ThemePick } from "../lib/prefs"

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

function Row({ title, sub, children }: { title: string; sub?: string; children: ReactNode }) {
  return (
    <div className="srow">
      <span style={{ flex: 1, display: "flex", flexDirection: "column", lineHeight: 1.35 }}>
        <span>{title}</span>
        {sub ? <span className="sub" style={{ fontSize: 11 }}>{sub}</span> : null}
      </span>
      {children}
    </div>
  )
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="stitle">{title}</h2>
      <div className="card" style={{ overflow: "hidden" }}>
        {children}
      </div>
    </section>
  )
}

/** Input level from the chosen microphone; only runs once the person has allowed the microphone. */
function useMicLevel(deviceId: string, on: boolean): number {
  const [level, setLevel] = useState(0)
  useEffect(() => {
    if (!on) return
    let stop = false
    let stream: MediaStream | null = null
    let ctx: AudioContext | null = null
    let raf = 0
    navigator.mediaDevices
      ?.getUserMedia({ audio: deviceId ? { deviceId: { exact: deviceId } } : true })
      .then((s) => {
        if (stop) return s.getTracks().forEach((t) => t.stop())
        stream = s
        ctx = new AudioContext()
        const an = ctx.createAnalyser()
        an.fftSize = 512
        ctx.createMediaStreamSource(s).connect(an)
        const buf = new Uint8Array(an.fftSize)
        const tick = () => {
          an.getByteTimeDomainData(buf)
          let peak = 0
          for (const v of buf) peak = Math.max(peak, Math.abs(v - 128))
          setLevel(Math.min(1, peak / 64))
          raf = requestAnimationFrame(tick)
        }
        tick()
      })
      .catch(() => setLevel(0))
    return () => {
      stop = true
      cancelAnimationFrame(raf)
      stream?.getTracks().forEach((t) => t.stop())
      void ctx?.close()
    }
  }, [deviceId, on])
  return level
}

const HOURS = Array.from({ length: 24 }, (_, h) => h)

export function Settings({ release }: { release: DesktopRelease | null }) {
  const { prefs, setPrefs, web, toast } = useStore()
  const version = useAppVersion()
  const [login, setLogin] = useState<boolean | null>(null)
  const [mics, setMics] = useState<MediaDeviceInfo[]>([])
  const [micOn, setMicOn] = useState(false)
  const [upd, setUpd] = useState<string>("")
  const [checked, setChecked] = useState<DesktopRelease | null>(release)
  const [editQuiet, setEditQuiet] = useState(false)
  const level = useMicLevel(prefs.micId, micOn)
  const checking = useRef(false)

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
    // Show the level meter straight away only when the microphone is already allowed.
    navigator.permissions
      ?.query({ name: "microphone" as PermissionName })
      .then((p) => setMicOn(p.state === "granted"))
      .catch(() => {})
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
    if (checking.current) return
    checking.current = true
    setUpd("Checking…")
    const latest = await desktopRelease()
    checking.current = false
    if (!latest) return setUpd("Couldn't check right now")
    setChecked(latest)
    const at = new Date().toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
    if (version && isNewer(latest.version, version)) setUpd(`Version ${latest.version} is available`)
    else setUpd(`Up to date · checked ${at}`)
  }

  const newer = version && checked && isNewer(checked.version, version)
  const notif: { key: keyof Prefs; title: string }[] = [
    { key: "notifyApprovals", title: "Approval needed" },
    { key: "notifyDone", title: "Assignment finished" },
    { key: "notifyFailed", title: "Run failed" },
  ]

  return (
    <div className="scroll fade" style={{ flex: 1 }}>
      <div className="hdr" style={{ alignItems: "baseline" }}>
        <h1 style={{ flex: 1 }}>Settings</h1>
        <span className="sub">Saved on this computer</span>
      </div>
      <div style={{ padding: "8px 24px 24px", display: "grid", gridTemplateColumns: "minmax(0, 1.6fr) minmax(0, 1fr)", gap: 18, alignItems: "start" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <Group title="General">
            {login !== null ? (
              <Row title="Open at login">
                <Toggle on={login} label="Open at login" onChange={(v) => void setLoginAtStartup(v)} />
              </Row>
            ) : null}
            <Row title="Show in menu bar">
              <Toggle on={prefs.tray} label="Show in menu bar" onChange={(v) => setPrefs({ tray: v })} />
            </Row>
            <Row title="Theme">
              <div className="seg" role="radiogroup" aria-label="Theme">
                {(["system", "light", "dark"] as ThemePick[]).map((t) => (
                  <button key={t} className={prefs.theme === t ? "on" : ""} role="radio" aria-checked={prefs.theme === t} onClick={() => setPrefs({ theme: t })}>
                    {t === "light" ? "Light" : t === "dark" ? "Dark" : "System"}
                  </button>
                ))}
              </div>
            </Row>
          </Group>
          <Group title="Shortcuts">
            <Row title="Quick Ask" sub="Works from any app">
              <span className="kbd">
                {MOD} {SHIFT} Space
              </span>
            </Row>
            <Row title="Push to talk" sub="Press to talk to your agent, press again to send">
              <span className="kbd">{ALT} Space</span>
            </Row>
            <Row title="Command bar">
              <span className="kbd">{MOD} K</span>
            </Row>
          </Group>
          <Group title="Notifications">
            {notif.map((n) => (
              <Row key={n.key} title={n.title}>
                <Toggle on={Boolean(prefs[n.key])} label={n.title} onChange={(v) => setPrefs({ [n.key]: v } as Partial<Prefs>)} />
              </Row>
            ))}
            <Row title="Quiet hours" sub={`${hourLabel(prefs.quietFrom)} to ${hourLabel(prefs.quietTo)}, weekdays, and all weekend. Failures still show.`}>
              <button className="btn btn-sm" aria-expanded={editQuiet} onClick={() => setEditQuiet((x) => !x)}>
                {editQuiet ? "Done" : "Edit"}
              </button>
              <Toggle on={prefs.quietHours} label="Quiet hours" onChange={(v) => setPrefs({ quietHours: v })} />
            </Row>
            {editQuiet ? (
              <div className="srow fade" style={{ gap: 8 }}>
                <label htmlFor="qfrom" className="sub">
                  From
                </label>
                <select id="qfrom" className="select select-sm" value={prefs.quietFrom} onChange={(e) => setPrefs({ quietFrom: Number(e.target.value) })}>
                  {HOURS.map((h) => (
                    <option key={h} value={h}>
                      {hourLabel(h)}
                    </option>
                  ))}
                </select>
                <label htmlFor="qto" className="sub">
                  to
                </label>
                <select id="qto" className="select select-sm" value={prefs.quietTo} onChange={(e) => setPrefs({ quietTo: Number(e.target.value) })}>
                  {HOURS.map((h) => (
                    <option key={h} value={h}>
                      {hourLabel(h)}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
          </Group>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <Group title="Microphone">
            <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
              <label htmlFor="mic" className="sub">
                Input
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
              {micOn ? (
                <div role="meter" aria-label="Input level" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(level * 100)} style={{ display: "flex", gap: 4 }}>
                  {Array.from({ length: 6 }, (_, i) => (
                    <span key={i} style={{ flex: 1, height: 4, borderRadius: 2, background: level * 6 > i ? "var(--br)" : "var(--s3)" }} />
                  ))}
                </div>
              ) : (
                <button className="link" style={{ alignSelf: "flex-start" }} onClick={() => setMicOn(true)}>
                  Test microphone
                </button>
              )}
            </div>
          </Group>
          <Group title="Updates">
            <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                  <span style={{ fontSize: 13 }}>{version ? `Version ${version}` : "Version"}</span>
                  <span className="sub" style={{ fontSize: 11 }}>
                    {upd || (newer ? `Version ${checked!.version} is available` : "Gravitre tells you when a new version is out")}
                  </span>
                </span>
                {newer ? (
                  <button className="btn btn-p btn-sm" onClick={() => web("/download")}>
                    Download
                  </button>
                ) : (
                  <button className="btn btn-sm" onClick={() => void checkUpdates()}>
                    Check for updates
                  </button>
                )}
              </div>
              {checked?.notes ? (
                <button className="link" style={{ alignSelf: "flex-start" }} onClick={() => web(checked.notes!)}>
                  Release notes ↗
                </button>
              ) : null}
            </div>
          </Group>
          <Group title="Manage on web">
            {WEB_LINKS.map((w) => (
              <button key={w.label} className="srow linkrow" onClick={() => web(w.path)}>
                <span style={{ flex: 1 }}>{w.label}</span>
                <Icon name="ext" size={13} style={{ color: "var(--t3)" }} />
              </button>
            ))}
          </Group>
        </div>
      </div>
    </div>
  )
}
