/**
 * Role permissions data: GET /api/org/role-permissions returns the role list,
 * one line per role, every capability with its area and per role access, and
 * how many people in this workspace hold each role (owners counted apart).
 */

export interface RoleCapability {
  key: string
  capability: string
  area?: string | null
  access: Record<string, boolean>
}

export interface RolePermissionsResponse {
  roles: string[]
  role_descriptions?: Record<string, string>
  capabilities: RoleCapability[]
  member_counts?: Record<string, number> | null
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
      name: roleName(role),
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
