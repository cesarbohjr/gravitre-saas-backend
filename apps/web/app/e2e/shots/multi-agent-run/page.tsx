import MultiAgentRunPage from "@/app/multi-agent-run/page"

import { ShotAuthProvider } from "../shot-auth"

/**
 * Multi-agent run for capture. Open with `?runId=swr_renewal_risk` (completed,
 * with contributions and a merged recommendation) or `?runId=swr_churn_audit`
 * (failed on a connector) to land with the inspector already open. Selecting a
 * run by click calls router.replace to the real route, which leaves the harness.
 */
export default function Page() {
  return (
    <ShotAuthProvider>
      <MultiAgentRunPage />
    </ShotAuthProvider>
  )
}
