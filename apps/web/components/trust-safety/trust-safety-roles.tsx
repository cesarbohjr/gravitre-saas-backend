"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import type { User } from "@/types/api"
import { Hero, Icon, Segmented } from "./ts-ui"

/** What each role can do: [area, capability, [admin, member, viewer]]. */
const CAPS: Array<[string, string, [boolean, boolean, boolean]]> = [
  ["Insights", "View dashboards and intelligence", [true, true, true]],
  ["Insights", "Run Gravitre AI and chat", [true, true, true]],
  ["Build", "Create agents and workflows", [true, true, false]],
  ["Build", "Install marketplace packs", [true, false, false]],
  ["Build", "Manage connectors", [true, true, false]],
  ["Govern", "Approve write actions", [true, true, false]],
  ["Govern", "Org settings and billing", [true, false, false]],
  ["Govern", "Invite and manage members", [true, false, false]],
  ["Govern", "Export the audit trail", [true, false, false]],
]

const ROLES = [
  { name: "Admin", desc: "Full control of the workspace, people and billing.", ico: "ts-ico sm" },
  { name: "Member", desc: "Builds and runs agents, approves day to day work.", ico: "ts-ico sm blue" },
  { name: "Viewer", desc: "Sees dashboards and asks Gravitre questions.", ico: "ts-ico sm warn" },
] as const

function people(n: number | null): string {
  if (n == null) return "Loading"
  if (n === 0) return "No one yet"
  return `${n} ${n === 1 ? "person" : "people"}`
}

export function TrustSafetyRoles() {
  const [view, setView] = useState<"matrix" | "role">("matrix")
  const [role, setRole] = useState(0)
  const team = useSWR<{ team?: User[] }>("/api/settings/team", fetcher, { revalidateOnFocus: false })

  const members = team.data?.team ?? null
  const countOf = (match: (r: string) => boolean) => (members ? members.filter((m) => match(String(m.role ?? "member").toLowerCase())).length : null)
  const counts = [countOf((r) => r === "owner" || r === "admin"), countOf((r) => r === "member"), countOf((r) => r === "viewer")]

  const cur = ROLES[role]
  const can = CAPS.filter((c) => c[2][role])
  const cannot = CAPS.filter((c) => !c[2][role])

  return (
    <>
      <Hero
        art="roles"
        eyebrow="Role permissions · access control"
        big={ROLES.length}
        unit="roles defined"
        advice="Roles decide who can approve writes, change policies and export the audit trail. They follow your organization's role definitions."
        actions={
          <>
            <Segmented label="View" value={view} onChange={setView} options={[["matrix", "Compare roles"], ["role", "One role"]] as const} />
            <Link href="/settings?section=team" className="ts-btn line sm">Invite people</Link>
          </>
        }
        tiles={[
          { value: counts[0] ?? "–", label: "Admins", tone: "good" },
          { value: counts[1] ?? "–", label: "Members" },
          { value: counts[2] ?? "–", label: "Viewers" },
          { value: CAPS.length, label: "Capabilities" },
        ]}
      />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
        {ROLES.map((r, i) => {
          const n = CAPS.filter((c) => c[2][i]).length
          return (
            <button
              key={r.name}
              type="button"
              className={`ts-wcard${view === "role" && role === i ? " sel" : ""}`}
              onClick={() => { setRole(i); setView("role") }}
              style={{ textAlign: "left", font: "inherit", color: "inherit" }}
            >
              <span style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ display: "flex", gap: 10, alignItems: "center" }}>
                  <span className={r.ico}><Icon name="shield" size={15} /></span>
                  <span style={{ fontWeight: 600, fontSize: 16 }}>{r.name}</span>
                </span>
                <span className="ts-mono" style={{ fontSize: 11, color: "#6A6B64" }}>{n} of {CAPS.length}</span>
              </span>
              <span style={{ fontSize: 13, color: "#55564F", lineHeight: 1.45 }}>{r.desc}</span>
              <span style={{ display: "flex", gap: 3 }} aria-hidden="true">
                {CAPS.map((c) => <span key={c[1]} style={{ flex: 1, height: 6, borderRadius: 3, background: c[2][i] ? "#19C37D" : "#E4E4DF" }} />)}
              </span>
              <span style={{ fontSize: 12, color: "#6A6B64" }}>{people(counts[i])}</span>
            </button>
          )
        })}
      </div>
      <section className="ts-card" style={{ overflow: "hidden" }}>
        {view === "matrix" ? (
          <div className="ts-tblwrap">
            <div style={{ minWidth: 560 }}>
              <div className="ts-tr" style={{ ["--cols" as string]: "minmax(0,1fr) 110px 110px 110px", padding: "0 20px", background: "#FBFBF9", borderBottom: "1px solid #EFEFEA" }}>
                <div className="ts-th" style={{ paddingLeft: 0 }}>Capability</div>
                <div className="ts-th" style={{ textAlign: "center" }}>Admin</div>
                <div className="ts-th" style={{ textAlign: "center" }}>Member</div>
                <div className="ts-th" style={{ textAlign: "center" }}>Viewer</div>
              </div>
              {CAPS.map(([area, label, cells]) => (
                <div key={label} className="ts-row" style={{ ["--cols" as string]: "minmax(0,1fr) 110px 110px 110px", padding: "0 20px", minHeight: 54 }}>
                  <div style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 14 }}>
                    <span className="ts-mono ts-area">{area}</span>
                    {label}
                  </div>
                  {cells.map((yes, i) => (
                    <div key={i} style={{ display: "flex", justifyContent: "center" }}>
                      {yes ? (
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
              {can.map((c) => <div key={c[1]} style={{ fontSize: 14, padding: "8px 0", borderTop: "1px solid #F3F3EF" }}>{c[1]}</div>)}
            </div>
            <div style={{ padding: 20 }}>
              <div style={{ fontWeight: 600, marginBottom: 10, color: "#6A6B64" }}>{cur.name} cannot</div>
              {cannot.map((c) => <div key={c[1]} style={{ fontSize: 14, padding: "8px 0", borderTop: "1px solid #F3F3EF", color: "#55564F" }}>{c[1]}</div>)}
              {cannot.length === 0 ? <div style={{ fontSize: 14, color: "#6A6B64" }}>Nothing. This role has full access.</div> : null}
            </div>
          </div>
        )}
      </section>
    </>
  )
}
