import { NextRequest } from "next/server"
import { proxyRunStepAction } from "@/lib/run-action-proxy"

interface RouteParams {
  params: Promise<{ id: string; stepId: string }>
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  const { id, stepId } = await params
  return proxyRunStepAction(request, id, stepId, "retry")
}
