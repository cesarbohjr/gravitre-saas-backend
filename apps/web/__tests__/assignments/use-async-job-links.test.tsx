// @vitest-environment jsdom
import React, { act, useEffect } from "react"
import { createRoot } from "react-dom/client"
import { afterEach, expect, it, vi } from "vitest"

const state = vi.hoisted(() => ({ fetch: vi.fn() }))
vi.mock("@/lib/fetcher", () => ({ apiFetch: state.fetch }))
vi.mock("@/lib/agent-interrupts", () => ({ requestAgentInterrupt: vi.fn() }))

import { useAsyncJob, type SubmitAgentJobOptions } from "@/hooks/use-async-job"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

type Submit = (task: string, options?: SubmitAgentJobOptions) => Promise<unknown>
const probe: { submit: Submit | null } = { submit: null }
function Probe({ onReady }: { onReady: (submit: Submit) => void }) {
  const { submitJob } = useAsyncJob()
  useEffect(() => {
    onReady(submitJob)
  }, [onReady, submitJob])
  return null
}

afterEach(() => {
  vi.clearAllMocks()
  vi.useRealTimers()
})

async function bodyFor(options: SubmitAgentJobOptions): Promise<Record<string, unknown>> {
  vi.useFakeTimers()
  state.fetch.mockResolvedValue({ ok: true, json: async () => ({ jobId: "j1", status: "queued" }) })
  const root = createRoot(document.createElement("div"))
  act(() => root.render(<Probe
        onReady={(fn) => {
          probe.submit = fn
        }}
      />))
  await act(async () => {
    await probe.submit!("Do the thing", options)
  })
  act(() => root.unmount())
  const [, init] = state.fetch.mock.calls.find(([url]) => url === "/api/agent-jobs")!
  return JSON.parse((init as RequestInit).body as string)
}

it("sends the goal and work object a job counts toward", async () => {
  const body = await bodyFor({ agentId: "a1", goalId: "g1", workObjectId: "w1" })
  expect(body).toMatchObject({ task: "Do the thing", agent_id: "a1", goal_id: "g1", work_object_id: "w1" })
})

it("leaves the link fields out when there is no goal", async () => {
  const body = await bodyFor({ agentId: "a1" })
  expect(body).not.toHaveProperty("goal_id")
  expect(body).not.toHaveProperty("work_object_id")
})
