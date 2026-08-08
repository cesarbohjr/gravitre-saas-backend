/**
 * Progressive disclosure helpers composing seat type + plan tier + Meson addons.
 * One shared shell — never a second Lite product tree.
 */

export type SeatMembership = {
  is_lite?: boolean
  is_full_seat?: boolean
  is_admin?: boolean
  is_department_manager?: boolean
  department?: { id: string; name: string } | null
}

export type NavAccessFlags = {
  isLite: boolean
  isFullSeat: boolean
  isOrgAdmin: boolean
  isDepartmentManager: boolean
  hasMesonBuilder: boolean
  hasAddon: (code: string) => boolean
  canAccessFeature: (feature: string) => boolean
}

/** BUILD nav items require a full seat (A1). Shown locked for Lite with honest copy. */
export const BUILD_NAV_HREFS = new Set([
  "/marketplace",
  "/workflows",
  "/connectors",
  "/sources",
])

/**
 * B1 voice CONFIGURE: full seats or department managers (not Lite members).
 * Lite may USE voice on assigned department agents when voice_interface is on.
 */
export function canConfigureVoice(membership: SeatMembership | null | undefined): boolean {
  if (!membership) return false
  if (membership.is_full_seat) return true
  if (membership.is_admin && !membership.is_lite) return true
  if (membership.is_department_manager) return true
  if (membership.is_lite) return false
  // Fail closed for unknown seat shape when Lite flag is absent but not full.
  return Boolean(membership.is_full_seat || membership.is_department_manager)
}

export function buildNavLockedReason(flags: NavAccessFlags, href: string): string | null {
  if (!flags.isLite) return null
  if (BUILD_NAV_HREFS.has(href.split("?")[0])) {
    return "Requires a full seat"
  }
  if (href.startsWith("/workflows") && !flags.hasMesonBuilder) {
    return "Requires Control plan or higher"
  }
  return null
}
