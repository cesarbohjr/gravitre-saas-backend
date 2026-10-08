import { Suspense } from "react"

import AssignmentDetailPage from "@/app/(app)/assignments/[id]/page"

import { ShotAuthProvider } from "../shot-auth"

/**
 * Assignment detail for capture. The page reads `params` via `use()`, so it
 * needs its own route. The job is a delivered fixture blocked by a plan limit.
 */
export default function Page() {
  return (
    <ShotAuthProvider>
      <Suspense fallback={null}>
        <AssignmentDetailPage params={Promise.resolve({ id: "job_shot_blocked" })} />
      </Suspense>
    </ShotAuthProvider>
  )
}
