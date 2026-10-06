import { Suspense } from "react"
import { ShotSurface } from "../shot-view"

export default function Page() {
  return (
    <Suspense>
      <ShotSurface name="lite-assign" />
    </Suspense>
  )
}
