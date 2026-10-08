import { Suspense } from "react"

import ModelDetailPage from "@/app/(app)/models/[id]/page"

import { ShotAuthProvider } from "../shot-auth"

/** Model detail for capture: a deployed classifier with three versions. */
export default function Page() {
  return (
    <ShotAuthProvider>
      <Suspense fallback={null}>
        <ModelDetailPage params={Promise.resolve({ id: "mdl_churn" })} />
      </Suspense>
    </ShotAuthProvider>
  )
}
