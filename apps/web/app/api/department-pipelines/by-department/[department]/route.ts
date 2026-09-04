import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ department: string }> },
) {
  const { department } = await context.params
  return proxyToFastApi(
    request,
    `/api/department-pipelines/by-department/${encodeURIComponent(department)}`,
  )
}
