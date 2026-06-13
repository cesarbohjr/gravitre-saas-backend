import { NextRequest } from "next/server"
import { proxyRunAction } from "@/lib/run-action-proxy"

interface RouteParams {
  params: Promise<{ id: string }>
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  const { id } = await params
  return proxyRunAction(request, id, "resume-paused")
}
