import ActivityPage from "@/app/activity/page"
import ApprovalsPage from "@/app/approvals/page"
import ConnectorsPage from "@/app/connectors/page"

import { ShotAuthProvider } from "./shot-auth"

/**
 * Real product surfaces available for capture.
 *
 * Deliberately static routes rather than one `[view]` dynamic segment: under
 * this layout the dynamic param came through empty, so every request fell into
 * the `notFound()` branch and looked like a routing/auth failure. Static
 * children are unambiguous and cheap here — there are only a few surfaces.
 */
export const SHOT_SURFACES = {
  activity: ActivityPage,
  approvals: ApprovalsPage,
  connectors: ConnectorsPage,
} as const

export function ShotSurface({ name }: { name: keyof typeof SHOT_SURFACES }) {
  const Surface = SHOT_SURFACES[name]
  return (
    <ShotAuthProvider>
      <Surface />
    </ShotAuthProvider>
  )
}
