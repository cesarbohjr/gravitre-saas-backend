import { notFound } from "next/navigation"

import { ExecutionResultHarness } from "./harness"

export default async function ExecutionResultE2EPage({
  searchParams,
}: {
  searchParams: Promise<{ scenario?: string }>
}) {
  if (
    process.env.NEXT_PUBLIC_PLAYWRIGHT_E2E !== "1" &&
    process.env.PLAYWRIGHT_E2E !== "1"
  ) {
    notFound()
  }

  const params = await searchParams
  const scenario = params.scenario ?? "apollo_external"

  return <ExecutionResultHarness scenario={scenario} />
}
