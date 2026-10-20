"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import { ROLE_PERMISSIONS_KEY, buildRoleCards, type RolePermissionsResponse } from "@/lib/settings-api/roles"
import { Hero, Icon, Segmented } from "./ts-ui"

/** Fallback descriptions when the server sends none. */
const DESCRIPTIONS: Record<string, string> = {
  admin: "Full control of the workspace, people and billing.",
  member: "Builds and runs agents, approves day to day work.",
  viewer: "Sees dashboards and asks Gravitre questions.",
}
const ICO = ["ts-ico sm", "ts-ico sm blue", "ts-ico sm warn"]

export function TrustSafetyRoles() {
  const [view, setView] = useState<"matrix" | "role">("matrix")
  const [role, setRole] = useState(0)
  const { data: raw, error, mutate } = useSWR<RolePermissionsResponse>(ROLE_PERMISSIONS_KEY, fetcher, { revalidateOnFocus: false })
  const data = raw && Array.isArray(raw.roles) && Array.isArray(raw.capabilities) ? raw : undefined

  const cards = useMemo(() => (data ? buildRoleCards(data) : []), [data])
  const caps = data?.capabilities ?? []
  const cur = cards[role] ?? cards[0] ?? null
  const countOf = (r: string) => cards.find((c) => c.role === r)?.people ?? null
  const cols = `minmax(0,1fr) ${cards.map(() => "110px").join(" ")}`

  const loading = !data && !error
  return (
    <>
      <Hero
        art="roles"
        eyebrow="Role permissions · access control"
        big={data ? cards.length : "–"}
        unit="roles defined"
        advice={error && !data ? "Role permissions could not be loaded." : "Roles decide who can approve writes, change policies and export the audit trail. They follow your organization's role definitions."}
        actions={
          <>
            <Segmented label="View" value={view} onChange={setView} options={[["matrix", "Compare roles"], ["role", "One role"]] as const} />
            <Link href="/settings?section=team" className="ts-btn line sm">Invite people</Link>
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
      {cards.length > 0 ? (
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
        ) : view === "matrix" || !cur ? (
          <div className="ts-tblwrap">
            <div style={{ minWidth: 560 }}>
              <div className="ts-tr" style={{ ["--cols" as string]: cols, padding: "0 20px", background: "#FBFBF9", borderBottom: "1px solid #EFEFEA" }}>
                <div className="ts-th" style={{ paddingLeft: 0 }}>Capability</div>
                {cards.map((c) => <div key={c.role} className="ts-th" style={{ textAlign: "center" }}>{c.name}</div>)}
              </div>
              {caps.map((cap) => (
                <div key={cap.key} className="ts-row" style={{ ["--cols" as string]: cols, padding: "0 20px", minHeight: 54 }}>
                  <div style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 14 }}>
                    {cap.area ? <span className="ts-mono ts-area">{cap.area}</span> : null}
                    {cap.capability}
                  </div>
                  {cards.map((c) => (
                    <div key={c.role} style={{ display: "flex", justifyContent: "center" }}>
                      {cap.access[c.role] ? (
                        <span role="img" aria-label="Allowed" style={{ width: 26, height: 26, borderRadius: "50%", background: "#E8F5EE", color: "#0B8A5C", display: "grid", placeItems: "center" }}>
                          <Icon name="tick" size={15} width={2.4} />
                        </span>
                      ) : (
                        <span role="img" aria-label="Not allowed" style={{ width: 26, height: 26, display: "grid", placeItems: "center", color: "#B4B5AE" }}>
                          <Icon name="dash" size={15} width={2.2} />
                        </span>
                      )}
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
    </>
  )
}
