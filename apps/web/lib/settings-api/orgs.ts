/**
 * Organizations page data: GET /api/organizations returns every org the person
 * belongs to with their role, plan on record and exact member, agent and
 * workflow counts (null when a count could not be read).
 */
import type { Organization } from "@/types/api"

export interface OrgListItem extends Organization {
  role?: string | null
  plan_code?: string | null
  plan_name?: string | null
  plan_status?: string | null
  member_count?: number | null
  agent_count?: number | null
  workflow_count?: number | null
}

export const ORGS_KEY = "organizations:list"
export const ORGS_DOCS_HREF = "/docs/guides/how-to/settings#organization"

export function filterOrgs(orgs: OrgListItem[], query: string): OrgListItem[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return orgs
  return orgs.filter((org) => `${org.name ?? ""} ${org.slug ?? ""}`.toLowerCase().includes(needle))
}

/** Current org first, then by name. */
export function sortOrgs(orgs: OrgListItem[], currentId: string | null): OrgListItem[] {
  return [...orgs].sort((a, b) => {
    if (a.id === currentId) return -1
    if (b.id === currentId) return 1
    return String(a.name ?? "").localeCompare(String(b.name ?? ""))
  })
}

export function planLabel(org: OrgListItem): string | null {
  const name = org.plan_name || (org.plan ? org.plan.charAt(0).toUpperCase() + org.plan.slice(1) : null)
  if (!name) return null
  const status = String(org.plan_status ?? "").toLowerCase()
  if (status === "trialing") return `${name} (trial)`
  if (status === "past_due") return `${name} (payment past due)`
  if (status === "canceled" || status === "cancelled") return `${name} (cancelled)`
  return name
}

export function roleName(role: string | null | undefined): string {
  const value = String(role ?? "member").trim().toLowerCase() || "member"
  return value.charAt(0).toUpperCase() + value.slice(1)
}

/** "Mar 2026" style month for the Created row. */
export function createdLabel(iso: string | null | undefined): string | null {
  if (!iso) return null
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleDateString(undefined, { month: "short", year: "numeric" })
}

/** Exact count, or "n/a" when the server could not count it (never a made up zero). */
export function countLabel(value: number | null | undefined): string {
  return typeof value === "number" ? value.toLocaleString() : "n/a"
}
