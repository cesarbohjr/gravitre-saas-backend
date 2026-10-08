import { Suspense } from "react"

import GoalDetailPage from "@/app/(app)/goals/[id]/page"

import { ShotAuthProvider } from "../../shot-auth"

/** Open /e2e/shots/goal-detail/goal_pipeline. */
export default function Page() {
  return (
    <ShotAuthProvider>
      <Suspense fallback={null}>
        <GoalDetailPage />
      </Suspense>
    </ShotAuthProvider>
  )
}
