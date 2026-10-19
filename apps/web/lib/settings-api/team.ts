/**
 * Team members data. Members come from GET /api/settings/team (organization
 * memberships joined to public.users). Pending invites come from
 * GET /api/org/invites: an invite attaches the membership right away, so a
 * member is "pending" while their invited auth user has not accepted.
 */
import { apiFetch } from "@/lib/fetcher"
import { extractApiErrorMessage } from "@/lib/api-error-message"
import type { User } from "@/types/api"

export type TeamRole = "owner" | "admin" | "member" | "viewer"
export type TeamStatus = "active" | "pending"
export type TeamTab = "all" | "active" | "pending"

/** Roles an admin can give through the invite form (backend: admin|member|viewer). */
export const INVITE_ROLES: { id: Exclude<TeamRole, "owner">; label: string }[] = [
  { id: "admin", label: "Admin" },
  { id: "member", label: "Member" },
  { id: "viewer", label: "Viewer" },
]

export interface TeamApiMember extends User {
  membershipId?: string | null
  orgId?: string | null
  userId?: string | null
  name?: string | null
}

export interface PendingInvite {
  user_id: string
  email: string | null
  role: string
  invited_at: string | null
}

export interface InvitesResponse {
  invites: PendingInvite[]
  checked?: number
  unchecked?: number
}

export interface TeamRow {
  key: string
  /** public.users id (what the existing edit/remove endpoints take). */
  id: string | null
  /** auth user id (what the org membership endpoints take). */
  userId: string | null
  name: string
  email: string | null
  avatarUrl: string | null
  subtitle: string | null
  role: TeamRole
  status: TeamStatus
  invitedAt: string | null
  member: TeamApiMember | null
}

export const TEAM_KEY = "/api/settings/team"
export const INVITES_KEY = "/api/org/invites"
export const LITE_SEATS_KEY = "/api/settings/lite-seats"

export function normalizeRole(role: unknown): TeamRole {
  const value = String(role ?? "member").trim().toLowerCase()
  return value === "owner" || value === "admin" || value === "viewer" ? value : "member"
}

export function roleTitle(role: TeamRole): string {
  return role.charAt(0).toUpperCase() + role.slice(1)
}

/** Merge memberships with pending invites. Invites with no member row still show (by email). */
export function buildTeamRows(members: TeamApiMember[], invites: PendingInvite[] | null | undefined): TeamRow[] {
  const pendingByUser = new Map((invites ?? []).map((invite) => [invite.user_id, invite]))
  const seen = new Set<string>()
  const rows: TeamRow[] = members.map((member) => {
    const userId = member.userId ? String(member.userId) : null
    const invite = userId ? pendingByUser.get(userId) : undefined
    if (userId) seen.add(userId)
    const email = member.email ?? invite?.email ?? null
    return {
      key: String(member.membershipId ?? member.id ?? userId ?? email),
      id: member.id ?? null,
      userId,
      name: (member.full_name || member.name || "").trim() || (email ? email.split("@")[0] : "Unnamed member"),
      email,
      avatarUrl: member.avatar_url ?? null,
      subtitle: [member.job_title, member.department].filter(Boolean).join(" · ") || null,
      role: normalizeRole(member.role),
      status: invite ? "pending" : "active",
      invitedAt: invite?.invited_at ?? null,
      member,
    }
  })
  for (const invite of invites ?? []) {
    if (seen.has(invite.user_id)) continue
    rows.push({
      key: `invite-${invite.user_id}`,
      id: null,
      userId: invite.user_id,
      name: invite.email ? invite.email.split("@")[0] : "Invited member",
      email: invite.email,
      avatarUrl: null,
      subtitle: null,
      role: normalizeRole(invite.role),
      status: "pending",
      invitedAt: invite.invited_at,
      member: null,
    })
  }
  return rows
}

export function teamCounts(rows: TeamRow[]) {
  const active = rows.filter((row) => row.status === "active")
  return {
    all: rows.length,
    active: active.length,
    pending: rows.length - active.length,
    /** Active people on a full seat (owners, admins and members; viewers are Lite). */
    fullSeats: active.filter((row) => row.role !== "viewer").length,
  }
}

export function filterTeamRows(rows: TeamRow[], tab: TeamTab, query: string): TeamRow[] {
  const needle = query.trim().toLowerCase()
  return rows.filter((row) => {
    if (tab !== "all" && row.status !== tab) return false
    if (!needle) return true
    return `${row.name} ${row.email ?? ""}`.toLowerCase().includes(needle)
  })
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await apiFetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(extractApiErrorMessage(payload) ?? `Request failed: ${response.status}`)
  }
  return payload as T
}

export const teamApi = {
  resendInvite: (userId: string) =>
    postJson<{ ok: boolean; email: string }>(`/api/org/invites/${encodeURIComponent(userId)}/resend`, {}),
}
