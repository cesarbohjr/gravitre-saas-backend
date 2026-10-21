"use client"

import { useState } from "react"
import { toast } from "sonner"
import { enterpriseApi } from "@/lib/api"
import type { EnterpriseSiemConfig, EnterpriseSiemEventType } from "@/types/api"
import { Icon, Pill, Switch, TONE } from "./ts-ui"

type SiemData = { data?: EnterpriseSiemConfig; error?: unknown; mutate: (next?: EnterpriseSiemConfig, opts?: { revalidate: boolean }) => Promise<unknown> }

export const SIEM_EVENT_TYPES: ReadonlyArray<readonly [EnterpriseSiemEventType, string]> = [
  ["audit", "Audit events"],
  ["auth", "Sign in and access"],
  ["approvals", "Approval decisions"],
  ["policy", "Policy changes"],
  ["agent", "Agent runs"],
]
const ALL_EVENTS = SIEM_EVENT_TYPES.map(([id]) => id)

const isHttpsUrl = (value: string) => /^https:\/\/\S+\.\S+/i.test(value.trim())

export function siemForwarding(data: EnterpriseSiemConfig | undefined) {
  return Boolean(data?.enabled && data.endpoint && isHttpsUrl(data.endpoint))
}

/** A fresh signing secret, generated in the browser and shown until it is saved. */
function newSecret() {
  const bytes = new Uint8Array(16)
  crypto.getRandomValues(bytes)
  return `whsec_${Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("")}`
}

/**
 * SIEM export through GET/PUT /api/enterprise/siem and POST /api/enterprise/siem/test.
 * A saved secret is never sent back, so Reveal only shows a secret made here
 * with Rotate (or the first one, before anything is saved).
 */
export function TrustSafetySiem({ siem }: { siem: SiemData }) {
  const { data, error, mutate } = siem
  const [enabled, setEnabled] = useState(false)
  const [endpoint, setEndpoint] = useState("")
  const [events, setEvents] = useState<EnterpriseSiemEventType[]>(ALL_EVENTS)
  const [draftSecret, setDraftSecret] = useState<string | null>(null)
  const [reveal, setReveal] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [tested, setTested] = useState<string | null>(null)
  const [seed, setSeed] = useState<string | null>(null)

  const nextSeed = data ? `${data.enabled}|${data.endpoint ?? ""}|${data.hasSecret}|${(data.events ?? ALL_EVENTS).join(",")}` : null
  if (nextSeed && nextSeed !== seed) {
    setSeed(nextSeed)
    setEnabled(Boolean(data?.enabled))
    setEndpoint(data?.endpoint ?? "")
    setEvents(data?.events ?? ALL_EVENTS)
    setDraftSecret(data?.hasSecret ? null : newSecret())
    setReveal(false)
  }

  if (error && !data) {
    return (
      <>
        <SiemHead pill={{ ...TONE.mute, label: "Unavailable" }} />
        <section className="ts-card" style={{ padding: 20, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", fontSize: 13, color: "#8A2530" }}>
          SIEM export did not load.
          <button type="button" className="ts-btn line sm" onClick={() => void mutate()}>Try again</button>
        </section>
      </>
    )
  }
  if (!data) {
    return (
      <>
        <SiemHead pill={{ ...TONE.mute, label: "Loading" }} />
        <section className="ts-card" style={{ padding: 20, fontSize: 13, color: "#6A6B64" }} role="status">Loading SIEM export</section>
      </>
    )
  }

  const url = endpoint.trim()
  const urlOk = isHttpsUrl(url)
  const urlBad = url.length > 0 && !urlOk
  const dirty =
    enabled !== data.enabled ||
    url !== (data.endpoint ?? "") ||
    // The first secret is drafted on load; it only counts as a change when it replaces a saved one.
    (draftSecret !== null && data.hasSecret) ||
    events.join(",") !== (data.events ?? ALL_EVENTS).join(",")
  const pill = enabled && urlOk
    ? { ...TONE.ok, dot: "#19C37D", live: true, label: "Forwarding on" }
    : enabled
      ? { ...TONE.warn, label: "Needs an endpoint" }
      : { ...TONE.mute, label: "Forwarding off" }

  const save = async () => {
    if (urlBad) {
      toast.error("Use an https endpoint")
      return
    }
    if (enabled && !urlOk) {
      toast.error("Add an https endpoint before turning forwarding on")
      return
    }
    setSaving(true)
    try {
      const payload: Parameters<typeof enterpriseApi.updateSiem>[0] = { enabled, endpoint: url, events }
      if (draftSecret) payload.secret = draftSecret
      const updated = await enterpriseApi.updateSiem(payload)
      await mutate(updated, { revalidate: false })
      setTested(null)
      toast.success("SIEM export saved")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save SIEM export")
    } finally {
      setSaving(false)
    }
  }

  const sendTest = async () => {
    setTesting(true)
    try {
      const result = await enterpriseApi.testSiem()
      if (result.ok) {
        setTested("Test event sent. Check your SIEM for an enterprise.siem.test event.")
      } else {
        setTested(result.message || `The test event was not delivered${result.status ? ` (${result.status})` : ""}.`)
      }
    } catch (err) {
      setTested(err instanceof Error ? err.message : "The test event was not delivered.")
    } finally {
      setTesting(false)
    }
  }

  const savedEndpointOk = Boolean(data.endpoint && isHttpsUrl(data.endpoint) && data.hasSecret)
  const testNote = tested
    ? tested
    : dirty
      ? "Save your changes, then send a test event."
      : savedEndpointOk
        ? "Send a test event to confirm the endpoint and signature."
        : "Add an https endpoint to send a test event."

  const toggleEvent = (id: EnterpriseSiemEventType) =>
    setEvents((cur) => (cur.includes(id) ? cur.filter((e) => e !== id) : ALL_EVENTS.filter((e) => e === id || cur.includes(e))))

  return (
    <>
      <SiemHead pill={pill} />
      <section className="ts-card" style={{ overflow: "hidden" }}>
        <div className="ts-sec">
          <span className="ts-ico"><Icon name="forward" /></span>
          <div style={{ flex: "1 1 260px", minWidth: 0 }}>
            <div style={{ fontWeight: 600 }}>Forward events</div>
            <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 2 }}>When on, security and audit events are delivered to the endpoint below</div>
          </div>
          <Switch on={enabled} label="Forward events" onToggle={() => setEnabled((v) => !v)} />
        </div>
        <div className="ts-sec" style={{ alignItems: "flex-start" }}>
          <div style={{ flex: "1 1 320px", minWidth: 0, display: "flex", flexDirection: "column", gap: 6 }}>
            <label htmlFor="siem-url" style={{ fontSize: 13, color: "#55564F" }}>Endpoint URL</label>
            <div className={`ts-input${urlBad ? " bad" : ""}`} style={{ flex: "0 0 auto" }}>
              <input
                id="siem-url"
                type="url"
                placeholder="https://siem.example.com/webhooks/gravitre"
                value={endpoint}
                aria-invalid={urlBad}
                onChange={(e) => {
                  setEndpoint(e.target.value)
                  setTested(null)
                }}
              />
            </div>
            {urlBad ? <span style={{ fontSize: 12, color: "#8A2530" }}>Use an https endpoint</span> : null}
          </div>
          <div style={{ flex: "1 1 320px", minWidth: 0, display: "flex", flexDirection: "column", gap: 6 }}>
            <label htmlFor="siem-secret" style={{ fontSize: 13, color: "#55564F" }}>Signing secret</label>
            <div style={{ display: "flex", gap: 8 }}>
              <div className="ts-input" style={{ flex: "1 1 auto" }}>
                <Icon name="keySm" size={15} />
                <input
                  id="siem-secret"
                  className="ts-mono"
                  readOnly
                  value={reveal && draftSecret ? draftSecret : "•".repeat(32)}
                  style={{ fontSize: 13 }}
                />
              </div>
              <button
                type="button"
                className="ts-btn line sm"
                style={{ minHeight: 44 }}
                disabled={!draftSecret}
                title={draftSecret ? undefined : "A saved secret can't be shown again. Rotate to make a new one."}
                onClick={() => setReveal((v) => !v)}
              >
                {reveal && draftSecret ? "Hide" : "Reveal"}
              </button>
            </div>
            <span style={{ fontSize: 12, color: "#6A6B64" }}>
              Verify the X-Gravitre-Signature header with this secret.
              {draftSecret && data.hasSecret ? " The new secret takes effect when you save." : null}
              <button
                type="button"
                className="ts-btn text sm"
                style={{ minHeight: 0, padding: "0 4px", fontSize: 12 }}
                onClick={() => {
                  setDraftSecret(newSecret())
                  setReveal(true)
                }}
              >
                Rotate
              </button>
            </span>
          </div>
        </div>
        <div className="ts-sec">
          <div style={{ flex: "1 1 100%", display: "flex", flexDirection: "column", gap: 8 }}>
            <span style={{ fontSize: 13, color: "#55564F" }}>Events to send</span>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {SIEM_EVENT_TYPES.map(([id, label]) => {
                const on = events.includes(id)
                return (
                  <button key={id} type="button" className={`ts-chip${on ? " on" : ""}`} aria-pressed={on} onClick={() => toggleEvent(id)}>
                    {label}
                  </button>
                )
              })}
            </div>
          </div>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center", justifyContent: "space-between", padding: "14px 20px", borderTop: "1px solid #EFEFEA", background: "#FBFBF9" }}>
          <span style={{ fontSize: 13, color: "#6A6B64" }} role="status">{testNote}</span>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" className="ts-btn line sm" disabled={testing || dirty || !savedEndpointOk} onClick={() => void sendTest()}>
              {testing ? "Sending…" : "Send test event"}
            </button>
            <button type="button" className="ts-btn green sm" disabled={saving || !dirty || urlBad} onClick={() => void save()}>
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      </section>
    </>
  )
}

function SiemHead({ pill }: { pill: { bg: string; fg: string; dot: string; live?: boolean; label: string } }) {
  return (
    <div className="ts-sechead" style={{ marginTop: 8, justifyContent: "space-between" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <span className="ts-eyebrow">SIEM export</span>
        <span style={{ fontSize: 13, color: "#6A6B64" }}>Stream audit and security events to your SIEM by signed webhook</span>
      </div>
      <Pill bg={pill.bg} fg={pill.fg} dot={pill.dot} live={pill.live}>{pill.label}</Pill>
    </div>
  )
}
