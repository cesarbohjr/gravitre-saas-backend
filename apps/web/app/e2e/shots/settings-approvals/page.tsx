import { Suspense } from "react"

import { ShotSurface } from "../shot-view"

export default function Page() {
  return (
    <Suspense fallback={null}>
      <ShotSurface name="settings-approvals" />
    </Suspense>
  )
}
