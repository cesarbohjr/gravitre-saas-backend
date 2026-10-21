/**
 * Role permissions data: GET /api/org/role-permissions returns the role list,
 * one line per role, every capability with its area and per role access, and
 * how many people in this workspace hold each role (owners counted apart).
 * PUT /api/org/role-permissions (admins) replaces the whole role list: the
 * capabilities per role, new custom roles and deleted ones. The server enforces
 * the saved matrix on approvals, exports, installs, connectors, builds, team
 * and billing actions.
 */

import { apiFetch } from "@/lib/fetcher"
import { extractApiErrorMessage } from "@/lib/api-error-message"

export interface RoleCapability {
  key: string
  capability: string
  area?: string | null
  access: Record<string, boolean>
}

export interface RolePermissionsResponse {
  roles: string[]
  role_names?: Record<string, string>
  role_descriptions?: Record<string, string>
  /** Roles this workspace created; built in roles can't be deleted. */
  custom_roles?: string[]
  /** Roles whose capabilities can't change (admin always has everything). */
  locked_roles?: string[]
  capabilities: RoleCapability[]
  member_counts?: Record<string, number> | null
  /** The signed-in member's role and what it allows here. */
  my_role?: string | null
  my_capabilities?: string[]
}

export interface RoleCard {
  role: string
  name: string
  description: string | null
  allowed: number
  total: number
  /** One flag per capability, in matrix order. */
  bar: boolean[]
  /** null when the server could not count people. */
  people: number | null
  owners: number
  peopleLabel: string
  can: string[]
  cannot: string[]
}

export const ROLE_PERMISSIONS_KEY = "/api/org/role-permissions"

export function roleName(role: string): string {
  return role.charAt(0).toUpperCase() + role.slice(1)
}

export function peopleLabel(people: number | null, owners = 0): string {
  if (people === null) return "People count not available"
  if (people === 0) return "No one yet"
  const base = people === 1 ? "1 person" : `${people} people`
  if (owners > 0) return owners === people ? `${base}, ${owners === 1 ? "the owner" : "all owners"}` : `${base}, including ${owners} owner${owners === 1 ? "" : "s"}`
  return base
}

/** Owners hold every admin capability, so they count toward the Admin card. */
export function buildRoleCards(matrix: RolePermissionsResponse): RoleCard[] {
  const counts = matrix.member_counts ?? null
  return matrix.roles.map((role) => {
    const bar = matrix.capabilities.map((cap) => Boolean(cap.access[role]))
    const owners = role === "admin" && counts ? counts.owner ?? 0 : 0
    const people = counts ? (counts[role] ?? 0) + owners : null
    return {
      role,
      name: matrix.role_names?.[role] || roleName(role),
      description: matrix.role_descriptions?.[role] || null,
      allowed: bar.filter(Boolean).length,
      total: bar.length,
      bar,
      people,
      owners,
      peopleLabel: peopleLabel(people, owners),
      can: matrix.capabilities.filter((cap) => cap.access[role]).map((cap) => cap.capability),
      cannot: matrix.capabilities.filter((cap) => !cap.access[role]).map((cap) => cap.capability),
    }
  })
}

/** One role while it is being edited. ``key`` is empty for a role not saved yet. */
export interface RoleDraft {
  id: string
  key: string
  name: string
  description: string
  capabilities: string[]
  custom: boolean
  locked: boolean
  people: number | null
}

export const ROLE_NAME_MAX = 40
export const ROLE_DESCRIPTION_MAX = 160
export const MAX_ROLES = 20

export function draftsFromMatrix(matrix: RolePermissionsResponse): RoleDraft[] {
  const custom = new Set(matrix.custom_roles ?? [])
  const locked = new Set(matrix.locked_roles ?? ["admin"])
  const cards = buildRoleCards(matrix)
  return matrix.roles.map((role, i) => ({
    id: role,
    key: role,
    name: cards[i].name,
    description: matrix.role_descriptions?.[role] ?? "",
    capabilities: matrix.capabilities.filter((cap) => cap.access[role]).map((cap) => cap.key),
    custom: custom.has(role),
    locked: locked.has(role),
    people: cards[i].people,
  }))
}

/** A user-facing problem with the drafts, or null when they can be saved. */
export function draftProblem(drafts: RoleDraft[]): string | null {
  if (drafts.length > MAX_ROLES) return `A workspace can have at most ${MAX_ROLES} roles.`
  const seen = new Set<string>()
  for (const d of drafts) {
    const name = d.name.trim()
    if (!name) return "Every role needs a name."
    if (name.length > ROLE_NAME_MAX) return `Role names can be at most ${ROLE_NAME_MAX} characters.`
    if (d.description.trim().length > ROLE_DESCRIPTION_MAX) return `Role descriptions can be at most ${ROLE_DESCRIPTION_MAX} characters.`
    if (seen.has(name.toLowerCase())) return `Two roles are named ${name}.`
    seen.add(name.toLowerCase())
  }
  return null
}

export function draftsEqual(a: RoleDraft[], b: RoleDraft[]): boolean {
  if (a.length !== b.length) return false
  return a.every((d, i) => {
    const o = b[i]
    return (
      d.key === o.key &&
      d.name.trim() === o.name.trim() &&
      d.description.trim() === o.description.trim() &&
      [...d.capabilities].sort().join() === [...o.capabilities].sort().join()
    )
  })
}

export async function saveRolePermissions(drafts: RoleDraft[]): Promise<RolePermissionsResponse> {
  const roles = drafts.map((d) => ({
    ...(d.key ? { key: d.key } : {}),
    name: d.name.trim(),
    description: d.description.trim(),
    capabilities: d.capabilities,
  }))
  const response = await apiFetch(ROLE_PERMISSIONS_KEY, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ roles }),
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(extractApiErrorMessage(payload) || `Could not save roles (${response.status})`)
  return payload as RolePermissionsResponse
}
