"use client"

/**
 * Enterprise > SIEM export: stream audit and security events to a webhook
 * (GET/PUT /api/enterprise/siem, POST /api/enterprise/siem/test). Not one of
 * the design's seven sections, kept as an extra section in the same menu.
 */
import { useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { KeyRound, Send } from "lucide-react"
import { enterpriseApi } from "@/lib/api"
import type { EnterpriseSiemConfig } from "@/types/api"
import { SetError, SetNote, SetPill, SetSkeleton, SetSwitch } from "./settings-kit"

export function EnterpriseSiem({ isAdmin }: { isAdmin: boolean }) {
  const { data, error, isLoading, mutate } = useSWR<EnterpriseSiemConfig>("enterprise-siem", () => enterpriseApi.getSiem(), {
    revalidateOnFocus: false,
  })
  const [enabled, setEnabled] = useState(false)
  const [endpoint, setEndpoint] = useState("")
  const [secret, setSecret] = useState("")
  const [rotating, setRotating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [seed, setSeed] = useState<string | null>(null)

  const nextSeed = data ? `${data.enabled}|${data.endpoint ?? ""}|${data.hasSecret}` : null
  if (nextSeed && nextSeed !== seed) {
    setSeed(nextSeed)
    setEnabled(Boolean(data?.enabled))
    setEndpoint(data?.endpoint ?? "")
    setSecret("")
    setRotating(false)
  }

  const hasSecret = data?.hasSecret ?? false
  const showSecret = !hasSecret || rotating
  const endpointValid = !endpoint.trim() || /^https:\/\//i.test(endpoint.trim())

  const save = async () => {
    if (!isAdmin) return
    if (!endpointValid) {
      toast.error("Use an https endpoint")
      return
    }
    setSaving(true)
    try {
      // PUT /api/enterprise/siem takes the endpoint as a string (empty clears it).
      const payload: { enabled: boolean; endpoint: string; secret?: string | null } = {
        enabled,
        endpoint: endpoint.trim(),
      }
      if (showSecret && secret.trim()) payload.secret = secret.trim()
      const updated = await enterpriseApi.updateSiem(payload)
      await mutate(updated, { revalidate: false })
      setSecret("")
      setRotating(false)
      toast.success("SIEM export saved")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save SIEM export")
    } finally {
      setSaving(false)
    }
  }

  const test = async () => {
    setTesting(true)
    try {
      const result = await enterpriseApi.testSiem()
      if (result.ok) toast.success("Test event delivered")
      else toast.error(result.message || `Delivery failed${result.status ? ` (${result.status})` : ""}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Test delivery failed")
    } finally {
      setTesting(false)
    }
  }

  if (error && !data) {
    return (
      <section className="gs-card">
        <SetError message="SIEM export did not load." onRetry={() => void mutate()} />
      </section>
    )
  }
  if (isLoading || !data) {
    return (
      <section className="gs-card">
        <SetSkeleton rows={3} label="Loading SIEM export" />
      </section>
    )
  }

  const active = enabled && Boolean(data.endpoint || endpoint.trim())

  return (
    <>
      <div className="ent-intro">
        <p>Stream audit and security events to your SIEM by signed webhook.</p>
        <SetPill tone={active ? "green" : "neutral"} dot>
          {active ? "Forwarding on" : "Forwarding off"}
        </SetPill>
      </div>
      <section className="gs-card clip">
        <div className="gs-row-sec">
          <div className="gs-what">
            <b>Forward events</b>
            <span>When on, security and audit events are delivered to the endpoint below.</span>
          </div>
          <SetSwitch checked={enabled} onChange={setEnabled} label="Forward events to SIEM" disabled={!isAdmin} />
        </div>
        <div className="gs-row-sec">
          <label className="gs-field" style={{ flex: "1 1 100%" }}>
            Endpoint URL
            <input
              type="url"
              value={endpoint}
              onChange={(e) => setEndpoint(e.target.value)}
              placeholder="https://siem.yourcompany.com/ingest"
              disabled={!isAdmin}
              aria-invalid={!endpointValid}
              className="gs-mono"
            />
            {!endpointValid ? <span className="ent-field-err">Use an https endpoint</span> : null}
          </label>
        </div>
        <div className="gs-row-sec">
          <div className="gs-field" style={{ flex: "1 1 100%" }}>
            <span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
              <KeyRound size={14} aria-hidden /> Signing secret
            </span>
            {!showSecret ? (
              <span style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <span className="gs-mono" style={{ color: "var(--gs-muted)" }}>
                  {"•".repeat(20)}
                </span>
                <SetPill>Configured</SetPill>
                <button type="button" className="gs-btn text sm" disabled={!isAdmin} onClick={() => setRotating(true)}>
                  Rotate
                </button>
              </span>
            ) : (
              <span style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <input
                  type="password"
                  value={secret}
                  onChange={(e) => setSecret(e.target.value)}
                  placeholder={hasSecret ? "New secret" : "Signing secret"}
                  autoComplete="off"
                  disabled={!isAdmin}
                  aria-label="Signing secret"
                  style={{ flex: "1 1 220px" }}
                />
                {rotating ? (
                  <button
                    type="button"
                    className="gs-btn text sm"
                    onClick={() => {
                      setRotating(false)
                      setSecret("")
                    }}
                  >
                    Cancel
                  </button>
                ) : null}
              </span>
            )}
            <span className="hint">Payloads are HMAC signed with this secret. Leave it blank to keep the current one.</span>
          </div>
        </div>
        {isAdmin ? (
          <div className="gs-foot">
            <button type="button" className="gs-btn line sm" disabled={testing || !data.endpoint} onClick={() => void test()}>
              <Send size={14} aria-hidden />
              {testing ? "Sending…" : "Send test event"}
            </button>
            <button type="button" className="gs-btn dark sm" disabled={saving || !endpointValid} onClick={() => void save()}>
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        ) : null}
      </section>
      {!isAdmin ? <SetNote>Only workspace admins can configure SIEM export.</SetNote> : null}
    </>
  )
}
