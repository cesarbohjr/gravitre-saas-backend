"use client"

import { Fragment, useMemo, useState } from "react"
import useSWR from "swr"
import { toast } from "./overlays/toast"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import {
  ENVIRONMENTS_KEY,
  buildStages,
  countOrNull,
  environmentsSettingsApi,
  normalizeEnvironments,
  sumResource,
  type EnvResources,
  type EnvironmentsPayload,
  type StageId,
  type StageView,
} from "@/lib/settings-api/environments"
import { confirmTrustSafety } from "./overlays/confirm"
import { Hero, Icon, Note, Pill, Switch, TONE } from "./ts-ui"

const METRICS: Array<[keyof EnvResources, string]> = [["workflows", "Workflows"], ["agents", "Agents"], ["connectors", "Connectors"], ["sources", "Sources"]]

/** Environments from GET /api/environments; create, switch on or off and delete go to the same API. */
export function TrustSafetyEnvironments() {
  const { user } = useAuth()
  const { isAdmin } = useOrgAdmin()
  const { data, error, mutate } = useSWR<EnvironmentsPayload>(user ? ENVIRONMENTS_KEY : null, () => environmentsSettingsApi.list(), {
    revalidateOnFocus: false,
  })
  const envs = useMemo(() => normalizeEnvironments(data), [data])
  const stages = useMemo(() => buildStages(envs), [envs])
  const [picked, setPicked] = useState<StageId | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const env = stages.find((s) => s.id === picked) ?? stages.find((s) => s.env?.isDefault) ?? stages[2]
  const liveCount = stages.filter((s) => s.live).length
  const configured = stages.filter((s) => s.env).length
  const missing = stages.filter((s) => !s.env)
  const limit = typeof data?.environmentsLimit === "number" ? data.environmentsLimit : null
  const atLimit = limit !== null && envs.length >= limit
  const workflows = countOrNull(sumResource(envs, "workflows"))
  const agents = countOrNull(sumResource(envs, "agents"))

  const advice = !data
    ? error ? "Environments could not be loaded." : "Loading environments."
    : missing.length === 0
      ? "Every stage is set up. Promote changes from Development to Staging to Production."
      : `${missing.map((s) => s.name).join(" and ")} ${missing.length === 1 ? "is" : "are"} not set up yet. Add ${missing.length === 1 ? "it" : "them"} so changes are tested before they reach real records.`

  async function create(stage: StageView) {
    if (!isAdmin) return toast.error("Admin role required to create environments.")
    if (atLimit) return toast.error(`Your plan includes ${limit} environment${limit === 1 ? "" : "s"}. Upgrade to add more.`)
    setBusy(`create:${stage.id}`)
    try {
      await environmentsSettingsApi.create(stage.id)
      toast.success(`${stage.name} created`)
      setPicked(stage.id)
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error && err.message ? err.message : `Could not create ${stage.name}`)
    } finally {
      setBusy(null)
    }
  }

  async function toggleActive(stage: StageView) {
    if (!stage.env || !isAdmin) return
    const next = !stage.env.isActive
    setBusy(`toggle:${stage.id}`)
    try {
      await environmentsSettingsApi.setActive(stage.env.id, next)
      toast.success(`${stage.name} turned ${next ? "on" : "off"}`)
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error && err.message ? err.message : "Could not update environment")
    } finally {
      setBusy(null)
    }
  }

  async function remove(stage: StageView) {
    if (!stage.env || !isAdmin) return
    const ok = await confirmTrustSafety({
      title: `Delete ${stage.name}?`,
      description: "Workflows, agents, connectors and sources in this environment stop running here. This can't be undone.",
      confirmLabel: `Delete ${stage.name}`,
    })
    if (!ok) return
    setBusy(`delete:${stage.id}`)
    try {
      await environmentsSettingsApi.remove(stage.env.id)
      toast.success(`${stage.name} deleted`)
      setPicked(null)
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error && err.message ? err.message : "Could not delete environment")
    } finally {
      setBusy(null)
    }
  }

  const nextMissing = missing[0] ?? null

  return (
    <>
      <Hero
        art="envs"
        artState={{ stages: [Boolean(stages[0]?.live), Boolean(stages[1]?.live), Boolean(stages[2]?.live)] }}
        eyebrow="Environments · deployment"
        big={data ? liveCount : "–"}
        unit={`of ${stages.length} stages live`}
        bars={stages.map((s) => s.live)}
        advice={advice}
        actions={
          error && !data ? (
            <button type="button" className="ts-btn line sm" onClick={() => void mutate()}>Try again</button>
          ) : isAdmin && nextMissing && !atLimit ? (
            <button type="button" className="ts-btn dark sm" disabled={busy != null} onClick={() => void create(nextMissing)}>
              <Icon name="plus" size={15} width={2} />
              New environment
            </button>
          ) : null
        }
        tiles={[
          { value: data ? liveCount : "–", label: "Online", tone: "good" },
          { value: data ? `${configured} of ${stages.length}` : "–", label: "Configured" },
          { value: workflows ?? "None yet", label: "Workflows", muted: workflows == null },
          { value: agents ?? "None yet", label: "Agents", muted: agents == null },
        ]}
      />
      <section className="ts-card" style={{ padding: "20px 22px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <div>
            <div className="ts-eyebrow">Deployment pipeline</div>
            <div style={{ fontWeight: 600, marginTop: 4 }}>Promote changes stage by stage</div>
          </div>
          {data && missing.length > 0 ? (
            <Pill bg={TONE.warn.bg} fg={TONE.warn.fg} dot={TONE.warn.dot}>
              {missing.length} {missing.length === 1 ? "stage" : "stages"} not set up
            </Pill>
          ) : null}
        </div>
        <div aria-label="Pipeline stages" role="group" style={{ display: "flex", alignItems: "center", marginTop: 18, overflowX: "auto", paddingBottom: 4 }}>
          {stages.map((s, i) => {
            const tone = s.live ? TONE.ok : TONE.mute
            const lineC = s.live ? "#19C37D" : "#D3D3CC"
            const label = s.live ? "Active" : s.env ? "Off" : "Not set up"
            return (
              <Fragment key={s.id}>
                {i > 0 ? (
                  <svg width="64" height="20" viewBox="0 0 64 20" aria-hidden="true" style={{ flex: "0 0 auto" }}>
                    <path d="M4 10 H 60" stroke={lineC} strokeWidth="2" strokeDasharray="5 5" className="ts-flow2" />
                    <path d="M54 5 l6 5 -6 5" stroke={lineC} strokeWidth="2" fill="none" />
                  </svg>
                ) : null}
                <button
                  type="button"
                  className={`ts-wcard${env.id === s.id ? " sel" : ""}${s.live ? "" : " ts-ghost"}`}
                  aria-pressed={env.id === s.id}
                  onClick={() => setPicked(s.id)}
                  style={{ flex: "1 0 180px", textAlign: "left", font: "inherit", color: "inherit" }}
                >
                  <span style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span className={`ts-ico${s.live ? "" : " mute"}`}><Icon name="servers" /></span>
                    <Pill bg={tone.bg} fg={tone.fg} dot={s.live ? "#19C37D" : "#8A8B85"} live={s.live}>{label}</Pill>
                  </span>
                  <span style={{ fontWeight: 600 }}>{s.name}</span>
                  <span style={{ fontSize: 12, color: "#55564F" }}>{s.hint}</span>
                </button>
              </Fragment>
            )
          })}
        </div>
      </section>
      <div className="ts-cols">
        <div className="ts-colmain">
          <section className="ts-card" style={{ overflow: "hidden" }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "center", padding: "20px 22px", borderBottom: "1px solid #EFEFEA" }}>
              <span className="ts-ico" style={{ width: 48, height: 48, borderRadius: 14 }}><Icon name="servers" size={22} /></span>
              <div style={{ flex: "1 1 240px" }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <h3 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>{env.name}</h3>
                  {env.env?.isDefault ? <span className="ts-chip" style={{ cursor: "default", minHeight: 24 }}>Default</span> : null}
                </div>
                <div style={{ display: "flex", gap: 14, marginTop: 4, fontSize: 13, color: "#55564F" }}>
                  <span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
                    <span className={`ts-dot${env.live ? " ts-live" : ""}`} style={{ background: env.live ? "#19C37D" : "#8A8B85" }} />
                    {env.live ? "Active" : env.env ? "Off" : "Not set up"}
                  </span>
                  <span className="ts-mono" style={{ fontSize: 12 }}>{env.id}</span>
                </div>
              </div>
              {env.env && isAdmin && !env.env.isDefault ? (
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <Switch on={env.env.isActive} label={`Turn ${env.name} on`} disabled={busy != null} onToggle={() => void toggleActive(env)} />
                  <button type="button" className="ts-btn line sm" disabled={busy != null} onClick={() => void remove(env)}>Delete</button>
                </div>
              ) : null}
            </div>
            {env.env ? (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10, padding: "18px 22px" }}>
                  {METRICS.map(([key, label]) => {
                    const value = countOrNull(env.env?.resources[key] ?? null)
                    return (
                      <div key={key} className="ts-tile">
                        <span className="l">{label}</span>
                        <span style={{ fontSize: value == null ? 15 : 22, fontWeight: value == null ? 500 : 600, color: value == null ? "#55564F" : "#141513" }}>{value ?? "None yet"}</span>
                      </div>
                    )
                  })}
                </div>
                <div style={{ padding: "0 22px 20px" }}>
                  <div style={{ fontSize: 13, color: "#55564F", marginBottom: 6 }}>API endpoint</div>
                  <div className="ts-mono" style={{ background: "#F7F7F4", border: "1px solid #EFEFEA", borderRadius: 10, padding: "11px 12px", fontSize: 13, color: "#55564F", overflowWrap: "anywhere" }}>
                    {env.env.apiUrl ?? "No endpoint yet. It appears after the first deploy."}
                  </div>
                </div>
              </>
            ) : (
              <div style={{ padding: "32px 22px", display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: 10 }}>
                <div style={{ fontWeight: 600 }}>{env.name} is not set up</div>
                <p style={{ margin: 0, fontSize: 14, color: "#55564F", maxWidth: 420, lineHeight: 1.5 }}>{env.why}</p>
                {isAdmin ? (
                  <button type="button" className="ts-btn green sm" disabled={busy != null || atLimit} onClick={() => void create(env)}>
                    <Icon name="plus" size={15} width={2} />
                    Create {env.name}
                  </button>
                ) : (
                  <span style={{ fontSize: 13, color: "#55564F" }}>An owner or admin can create it.</span>
                )}
                {atLimit ? <span style={{ fontSize: 13, color: "#55564F" }}>Your plan includes {limit} environment{limit === 1 ? "" : "s"}.</span> : null}
              </div>
            )}
          </section>
        </div>
        <aside className="ts-colside" aria-label="Promotion rules">
          <section className="ts-card ts-side">
            <div className="ts-sidetitle"><span className="ts-ico sm"><Icon name="up" size={15} /></span>Promotion rules</div>
            <div className="ts-mini">
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 500 }}>Only admins promote</div>
                <div style={{ fontSize: 12, color: "#55564F" }}>Promoting a workflow version to Staging or Production needs the Admin role, and each promotion is written to the audit trail.</div>
              </div>
              <Pill bg={TONE.ok.bg} fg={TONE.ok.fg} dot={TONE.ok.dot}>Enforced</Pill>
            </div>
          </section>
          <Note><strong>Organization wide.</strong> Environment changes apply to everyone in this workspace.</Note>
        </aside>
      </div>
    </>
  )
}
