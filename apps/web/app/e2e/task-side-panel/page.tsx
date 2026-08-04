import { notFound } from "next/navigation"

import { TaskSidePanelHarness } from "./harness"

export default async function TaskSidePanelE2EPage({
  searchParams,
}: {
  searchParams: Promise<{ mode?: string }>
}) {
  if (
    process.env.NEXT_PUBLIC_PLAYWRIGHT_E2E !== "1" &&
    process.env.PLAYWRIGHT_E2E !== "1"
  ) {
    notFound()
  }

  const params = await searchParams
  const mode = params.mode ?? "on"

  return <TaskSidePanelHarness mode={mode} />
}
