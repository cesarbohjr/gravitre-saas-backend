"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { toast } from "@/components/agents/overlays/toast"
import { fetcher } from "@/lib/fetcher"
import { useOrgAdmin } from "@/lib/use-org-admin"
import {
  MAX_ROLES,
  ROLE_DESCRIPTION_MAX,
  ROLE_NAME_MAX,
  ROLE_PERMISSIONS_KEY,
  buildRoleCards,
  draftProblem,
  draftsEqual,
  draftsFromMatrix,
  saveRolePermissions,
  type RoleDraft,
  type RolePermissionsResponse,
} from "@/lib/settings-api/roles"
import { Hero, Icon, Note, Segmented } from "./ts-ui"

/** Fallback descriptions when the server sends none. */
const DESCRIPTIONS: Record<string, string> = {
  admin: "Full control of the workspace, people and billing.",
  member: "Builds and runs agents, approves day to day work.",
  viewer: "Sees dashboards and asks Gravitre questions.",
}
const ICO = ["ts-ico sm", "ts-ico sm blue", "ts-ico sm warn"]

function Mark({ on }: { on: boolean }) {
  return on ? (
    <span role="img" aria-label="Allowed" style={{ width: 26, height: 26, borderRadius: "50%", background: "#E8F5EE", color: "#0B8A5C", display: "grid", placeItems: "center" }}>
      <Icon name="tick" size={15} width={2.4} />
    </span>
  ) : (
    <span role="img" aria-label="Not allowed" style={{ width: 26, height: 26, display: "grid", placeItems: "center", color: "#B4B5AE" }}>
      <Icon name="dash" size={15} width={2.2} />
    </span>
  )
}

let nextDraftId = 0

export function TrustSafetyRoles() {
  const [view, setView] = useState<"matrix" | "role">("matrix")
  const [role, setRole] = useState(0)
  const { isAdmin, loading: adminLoading } = useOrgAdmin()
  const { data: raw, error, mutate } = useSWR<RolePermissionsResponse>(ROLE_PERMISSIONS_KEY, fetcher, { revalidateOnFocus: false })
  const data = raw && Array.isArray(raw.roles) && Array.isArray(raw.capabilities) ? raw : undefined

  const cards = useMemo(() => (data ? buildRoleCards(data) : []), [data])
  const caps = data?.capabilities ?? []
  const cur = cards[role] ?? cards[0] ?? null
  const countOf = (r: string) => cards.find((c) => c.role === r)?.people ?? null

  const [drafts, setDrafts] = useState<RoleDraft[] | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const original = useMemo(() => (data ? draftsFromMatrix(data) : []), [data])
  const editing = drafts !== null
  const dirty = editing && !draftsEqual(drafts, original)
  const problem = editing ? draftProblem(drafts) : null

  const columns = editing ? drafts : null
  const colCount = editing ? drafts.length : cards.length
  const cols = `minmax(0,1fr) ${Array.from({ length: colCount }, () => "110px").join(" ")}`

  function startEditing() {
    setDrafts(draftsFromMatrix(data!))
    setSaveError(null)
    setView("matrix")
  }

  function discard() {
    setDrafts(null)
    setSaveError(null)
  }

  function patch(id: string, change: Partial<RoleDraft>) {
    setDrafts((prev) => prev && prev.map((d) => (d.id === id ? { ...d, ...change } : d)))
  }

  function toggle(d: RoleDraft, capKey: string) {
    if (d.locked) return
    const has = d.capabilities.includes(capKey)
    patch(d.id, { capabilities: has ? d.capabilities.filter((k) => k !== capKey) : [...d.capabilities, capKey] })
  }

  function addRole() {
    setDrafts((prev) => {
      if (!prev || prev.length >= MAX_ROLES) return prev
      nextDraftId += 1
      const viewer = prev.find((d) => d.key === "viewer")
      return [
        ...prev,
        {
          id: `new-${nextDraftId}`,
          key: "",
          name: "",
          description: "",
          capabilities: viewer ? [...viewer.capabilities] : [],
          custom: true,
          locked: false,
          people: 0,
        },
      ]
    })
  }

  function removeRole(d: RoleDraft) {
    setDrafts((prev) => prev && prev.filter((x) => x.id !== d.id))
  }

  async function save() {
    if (!drafts || problem) return
    setSaving(true)
    setSaveError(null)
    try {
      const next = await saveRolePermissions(drafts)
      await mutate(next, { revalidate: false })
      setDrafts(null)
      toast.success("Role permissions saved")
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Could not save role permissions.")
    } finally {
      setSaving(false)
    }
  }

  const loading = !data && !error
  return (
    <>
      <Hero
        art="roles"
        eyebrow="Role permissions · access control"
        big={data ? cards.length : "–"}
        unit="roles defined"
        advice={
          error && !data
            ? "Role permissions could not be loaded."
            : "Roles decide who can approve writes, install packs, manage connectors and people, and export the audit trail. Changes apply to everyone on the role as soon as you save."
        }
        actions={
          <>
            {!editing ? <Segmented label="View" value={view} onChange={setView} options={[["matrix", "Compare roles"], ["role", "One role"]] as const} /> : null}
            {isAdmin && data && !editing ? (
              <button type="button" className="ts-btn dark sm" onClick={startEditing}>
                <Icon name="key" size={14} />Edit roles
              </button>
            ) : null}
            {!editing ? <Link href="/settings?section=team" className="ts-btn line sm">Invite people</Link> : null}
            {error && !data ? <button type="button" className="ts-btn line sm" onClick={() => void mutate()}>Try again</button> : null}
          </>
        }
        tiles={[
          { value: countOf("admin") ?? "–", label: "Admins", tone: "good" },
          { value: countOf("member") ?? "–", label: "Members" },
          { value: countOf("viewer") ?? "–", label: "Viewers" },
          { value: data ? caps.length : "–", label: "Capabilities" },
        ]}
      />

      {editing ? (
        <section className="ts-card" aria-label="Edit roles" style={{ padding: 20, display: "grid", gap: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 16 }}>Roles</div>
              <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 2 }}>Rename roles, describe them, add your own or delete ones nobody is on. Admin always keeps full access.</div>
            </div>
            <button type="button" className="ts-btn line sm" onClick={addRole} disabled={drafts.length >= MAX_ROLES}>
              <Icon name="plus" size={14} />New role
            </button>
          </div>
          {drafts.map((d) => {
            const deletable = d.custom && !d.people
            return (
              <div key={d.id} className="ts-roleedit">
                <label className="ts-input" style={{ flex: "1 1 180px" }}>
                  <input
                    value={d.name}
                    maxLength={ROLE_NAME_MAX}
                    placeholder="Role name"
                    aria-label={`Name of ${d.name || "new role"}`}
                    autoFocus={!d.key && !d.name}
                    onChange={(e) => patch(d.id, { name: e.target.value })}
                  />
                </label>
                <label className="ts-input" style={{ flex: "3 1 260px" }}>
                  <input
                    value={d.description}
                    maxLength={ROLE_DESCRIPTION_MAX}
                    placeholder="What this role is for"
                    aria-label={`Description of ${d.name || "new role"}`}
                    onChange={(e) => patch(d.id, { description: e.target.value })}
                  />
                </label>
                <span style={{ fontSize: 12, color: "#6A6B64", minWidth: 90 }}>
                  {d.custom ? (d.key ? (d.people ? `${d.people} ${d.people === 1 ? "person" : "people"}` : "No one yet") : "New") : "Built in"}
                </span>
                {d.custom ? (
                  <button
                    type="button"
                    className="ts-btn danger sm"
                    onClick={() => removeRole(d)}
                    disabled={!deletable}
                    title={deletable ? undefined : "Move the people on this role to another role first"}
                    aria-label={`Delete ${d.name || "new role"}`}
                  >
                    <Icon name="x" size={14} />Delete
                  </button>
                ) : (
                  <span style={{ width: 84 }} aria-hidden="true" />
                )}
              </div>
            )
          })}
        </section>
      ) : null}

      {!editing && cards.length > 0 ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
          {cards.map((c, i) => (
            <button
              key={c.role}
              type="button"
              className={`ts-wcard${view === "role" && cur?.role === c.role ? " sel" : ""}`}
              aria-pressed={view === "role" && cur?.role === c.role}
              onClick={() => { setRole(i); setView("role") }}
              style={{ textAlign: "left", font: "inherit", color: "inherit" }}
            >
              <span style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ display: "flex", gap: 10, alignItems: "center" }}>
                  <span className={ICO[i % ICO.length]}><Icon name="shield" size={15} /></span>
                  <span style={{ fontWeight: 600, fontSize: 16 }}>{c.name}</span>
                </span>
                <span className="ts-mono" style={{ fontSize: 11, color: "#6A6B64" }}>{c.allowed} of {c.total}</span>
              </span>
              <span style={{ fontSize: 13, color: "#55564F", lineHeight: 1.45 }}>{c.description ?? DESCRIPTIONS[c.role] ?? ""}</span>
              <span style={{ display: "flex", gap: 3 }} aria-hidden="true">
                {c.bar.map((on, k) => <span key={k} style={{ flex: 1, height: 6, borderRadius: 3, background: on ? "#19C37D" : "#E4E4DF" }} />)}
              </span>
              <span style={{ fontSize: 12, color: "#6A6B64" }}>{c.peopleLabel}</span>
            </button>
          ))}
        </div>
      ) : null}

      <section className="ts-card" style={{ overflow: "hidden" }}>
        {loading ? (
          <div style={{ padding: "28px 20px", fontSize: 14, color: "#6A6B64" }}>Loading role permissions.</div>
        ) : !data ? (
          <div style={{ padding: "28px 20px", fontSize: 14, color: "#8A2530" }}>Role permissions could not be loaded.</div>
        ) : caps.length === 0 ? (
          <div style={{ padding: "28px 20px", fontSize: 14, color: "#6A6B64" }}>Your organization has no role capabilities on record.</div>
        ) : view === "matrix" || editing || !cur ? (
          <div className="ts-tblwrap">
            <div style={{ minWidth: 560 }}>
              <div className="ts-tr" style={{ ["--cols" as string]: cols, padding: "0 20px", background: "#FBFBF9", borderBottom: "1px solid #EFEFEA" }}>
                <div className="ts-th" style={{ paddingLeft: 0 }}>Capability</div>
                {columns
                  ? columns.map((d) => <div key={d.id} className="ts-th" style={{ textAlign: "center", overflow: "hidden", textOverflow: "ellipsis" }}>{d.name.trim() || "New role"}</div>)
                  : cards.map((c) => <div key={c.role} className="ts-th" style={{ textAlign: "center" }}>{c.name}</div>)}
              </div>
              {caps.map((cap) => (
                <div key={cap.key} className="ts-row" style={{ ["--cols" as string]: cols, padding: "0 20px", minHeight: 54 }}>
                  <div style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 14 }}>
                    {cap.area ? <span className="ts-mono ts-area">{cap.area}</span> : null}
                    {cap.capability}
                  </div>
                  {columns
                    ? columns.map((d) => {
                        const on = d.locked || d.capabilities.includes(cap.key)
                        const who = d.name.trim() || "new role"
                        return (
                          <div key={d.id} style={{ display: "flex", justifyContent: "center" }}>
                            <button
                              type="button"
                              role="checkbox"
                              aria-checked={on}
                              aria-label={`${who}: ${cap.capability}`}
                              className={`ts-capbox${on ? " on" : ""}`}
                              disabled={d.locked}
                              title={d.locked ? "Admin always has every capability" : undefined}
                              onClick={() => toggle(d, cap.key)}
                            >
                              {on ? <Icon name="tick" size={14} width={2.6} /> : null}
                            </button>
                          </div>
                        )
                      })
                    : cards.map((c) => (
                        <div key={c.role} style={{ display: "flex", justifyContent: "center" }}>
                          <Mark on={Boolean(cap.access[c.role])} />
                        </div>
                      ))}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
            <div style={{ padding: 20, borderRight: "1px solid #EFEFEA" }}>
              <div style={{ fontWeight: 600, marginBottom: 10, color: "#1F6B42" }}>{cur.name} can</div>
              {cur.can.map((label) => <div key={label} style={{ fontSize: 14, padding: "8px 0", borderTop: "1px solid #F3F3EF" }}>{label}</div>)}
            </div>
            <div style={{ padding: 20 }}>
              <div style={{ fontWeight: 600, marginBottom: 10, color: "#6A6B64" }}>{cur.name} cannot</div>
              {cur.cannot.map((label) => <div key={label} style={{ fontSize: 14, padding: "8px 0", borderTop: "1px solid #F3F3EF", color: "#55564F" }}>{label}</div>)}
              {cur.cannot.length === 0 ? <div style={{ fontSize: 14, color: "#6A6B64" }}>Nothing. This role has full access.</div> : null}
            </div>
          </div>
        )}
      </section>

      {editing ? (
        <div className="ts-savebar" role="region" aria-label="Save role changes">
          <div style={{ flex: 1, minWidth: 0, fontSize: 14 }}>
            {saveError ? (
              <span role="alert" style={{ color: "#8A2530" }}>{saveError}</span>
            ) : problem ? (
              <span style={{ color: "#8A2530" }}>{problem}</span>
            ) : dirty ? (
              "Unsaved changes. Saving applies them to everyone on these roles right away."
            ) : (
              <span style={{ color: "#6A6B64" }}>No changes yet.</span>
            )}
          </div>
          <button type="button" className="ts-btn line sm" onClick={discard} disabled={saving}>Discard</button>
          <button type="button" className="ts-btn green sm" onClick={() => void save()} disabled={!dirty || Boolean(problem) || saving}>
            {saving ? "Saving" : "Save changes"}
          </button>
        </div>
      ) : null}

      {!isAdmin && !adminLoading && data ? <Note>Only owners and admins can change roles.</Note> : null}
    </>
  )
}
