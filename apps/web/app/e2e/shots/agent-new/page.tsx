import { Suspense } from "react"

import NewAgentPage from "@/app/(app)/agents/new/page"

import { ShotAuthProvider } from "../shot-auth"

export default function Page() {
  return (
    <ShotAuthProvider>
      <Suspense fallback={null}>
        <NewAgentPage />
      </Suspense>
    </ShotAuthProvider>
  )
}
