"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { Check, CircleCheck, CircleSlash, Columns3, ShieldCheck, UserRound, Users, X } from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { SettingsShell } from "@/components/settings/settings-shell"
import { SetError, SetPill, SetSkeleton, SetTabs } from "@/components/settings/settings-kit"
import { fetcher } from "@/lib/fetcher"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { useSettingsSectionNav } from "@/lib/settings-nav"
import {
  buildRoleCards,
  ROLE_PERMISSIONS_KEY,
  roleName,
  type RolePermissionsResponse,
} from "@/lib/settings-api/roles"
import "@/components/settings/roles.css"

type View = "matrix" | "role"

export default function PermissionsMatrixPage() {
  const { showAdmin, loading: adminLoading } = useOrgAdmin()
  const onSectionChange = useSettingsSectionNav("permissions")
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [view, setView] = useState<View>("matrix")
  const [selectedRole, setSelectedRole] = useState<string | null>(null)
  const { data, error, isLoading, mutate } = useSWR<RolePermissionsResponse>(ROLE_PERMISSIONS_KEY, fetcher, {
    revalidateOnFocus: false,
  })

  const cards = useMemo(() => (data ? buildRoleCards(data) : []), [data])
  const roles = data?.roles ?? []
  const capabilities = data?.capabilities ?? []
  const current = cards.find((card) => card.role === selectedRole) ?? cards[0] ?? null

  return (
    <AppShell title="Settings">
      <SettingsShell
        activeSection="permissions"
        isAdmin={showAdmin}
        mobileMenuOpen={mobileMenuOpen}
        onMobileMenuOpenChange={setMobileMenuOpen}
        onSectionChange={onSectionChange}
        hideHeader
      >
        <section className="roles-hero">
          <div>
            <SetPill tone="white">
              <ShieldCheck size={13} aria-hidden />
              Access control
            </SetPill>
            <h1>Role permissions</h1>
            <p>What each workspace role can do. Roles come from your organization&apos;s role definitions.</p>
          </div>
          <SetTabs<View>
            label="View"
            value={view}
            onChange={setView}
            options={[
              { id: "matrix", label: "Compare roles", icon: Columns3 },
              { id: "role", label: "One role", icon: UserRound, disabled: cards.length === 0 },
            ]}
          />
        </section>

        {error && !data ? (
          <section className="gs-card">
            <SetError message="Could not load role permissions." onRetry={() => void mutate()} />
          </section>
        ) : adminLoading || (isLoading && !data) ? (
          <>
            <div className="roles-cards" aria-hidden>
              {[0, 1, 2].map((i) => (
                <div key={i} className="gs-wcard" style={{ cursor: "default" }}>
                  <span className="gs-skel" style={{ height: 18, width: "40%" }} />
                  <span className="gs-skel" style={{ height: 14, width: "90%" }} />
                  <span className="gs-skel" style={{ height: 6, width: "100%" }} />
                </div>
              ))}
            </div>
            <section className="gs-card">
              <SetSkeleton rows={6} label="Loading role permissions" />
            </section>
          </>
        ) : capabilities.length === 0 ? (
          <section className="gs-card">
            <div className="gs-empty">
              <b>No role definitions yet</b>
              <p>Your organization has no role capabilities on record.</p>
            </div>
          </section>
        ) : (
          <>
            <div className="roles-cards">
              {cards.map((card) => (
                <button
                  key={card.role}
                  type="button"
                  className="gs-wcard"
                  aria-pressed={view === "role" && current?.role === card.role}
                  onClick={() => {
                    setSelectedRole(card.role)
                    setView("role")
                  }}
                  aria-label={`${card.name}: ${card.allowed} of ${card.total} capabilities, ${card.peopleLabel}`}
                >
                  <span className="roles-card-top">
                    <b>{card.name}</b>
                    <span className="gs-count">
                      {card.allowed} of {card.total}
                    </span>
                  </span>
                  {card.description ? <span className="roles-desc">{card.description}</span> : null}
                  <span className="roles-bar" aria-hidden>
                    {card.bar.map((on, index) => (
                      <span key={index} className={on ? "on" : undefined} style={{ animationDelay: `${index * 40}ms` }} />
                    ))}
                  </span>
                  <span className="roles-people">{card.peopleLabel}</span>
                </button>
              ))}
            </div>

            <section className="gs-card clip" aria-live="polite">
              {view === "matrix" ? (
                <div className="gs-scroll-x">
                  <div
                    className="gs-tbl roles-matrix"
                    role="table"
                    aria-label="Capabilities by role"
                    style={{ "--cols": `minmax(0, 1fr) ${roles.map(() => "110px").join(" ")}` } as React.CSSProperties}
                  >
                    <div className="gs-tr head" role="row">
                      <div className="gs-th" role="columnheader">
                        Capability
                      </div>
                      {roles.map((role) => (
                        <div key={role} className="gs-th" role="columnheader" style={{ textAlign: "center" }}>
                          {roleName(role)}
                        </div>
                      ))}
                    </div>
                    {capabilities.map((row) => (
                      <div key={row.key} className="gs-tr body" role="row">
                        <div className="roles-cap" role="rowheader">
                          {row.area ? <span className="roles-area">{row.area}</span> : null}
                          {row.capability}
                        </div>
                        {roles.map((role) => (
                          <div key={role} className="roles-cell" role="cell">
                            {row.access[role] ? (
                              <span className="roles-yes" aria-label={`${roleName(role)}: allowed`} role="img">
                                <Check size={15} aria-hidden />
                              </span>
                            ) : (
                              <span className="roles-no" aria-label={`${roleName(role)}: not allowed`} role="img">
                                <X size={15} aria-hidden />
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
              ) : current ? (
                <div className="roles-one">
                  <div>
                    <h3 style={{ color: "var(--gs-green-ink)" }}>
                      <CircleCheck size={17} aria-hidden />
                      {current.name} can
                    </h3>
                    {current.can.length > 0 ? (
                      <ul>
                        {current.can.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="gs-sub">Nothing yet. This role has no capabilities.</p>
                    )}
                  </div>
                  <div className="cannot">
                    <h3 style={{ color: "var(--gs-muted)" }}>
                      <CircleSlash size={17} aria-hidden />
                      {current.name} cannot
                    </h3>
                    {current.cannot.length > 0 ? (
                      <ul>
                        {current.cannot.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="gs-sub" style={{ fontSize: 14 }}>
                        Nothing. This role has full access.
                      </p>
                    )}
                  </div>
                </div>
              ) : null}
            </section>
            {data?.member_counts?.owner ? (
              <p className="gs-sub" style={{ margin: 0 }}>
                Owners have every Admin capability, and only an owner can change another owner or delete the workspace.
              </p>
            ) : null}
          </>
        )}

        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          <Link href="/settings?section=team" className="gs-btn line sm">
            <Users size={15} aria-hidden />
            Manage team
          </Link>
          <Link href="/settings" className="gs-btn text sm">
            Back to settings
          </Link>
        </div>
      </SettingsShell>
    </AppShell>
  )
}
