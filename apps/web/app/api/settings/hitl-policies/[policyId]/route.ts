import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ policyId: string }> },
) {
  const { policyId } = await context.params
  return proxyToFastApi(request, `/api/settings/hitl-policies/${policyId}`)
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ policyId: string }> },
) {
  const { policyId } = await context.params
  return proxyToFastApi(request, `/api/settings/hitl-policies/${policyId}`)
}
