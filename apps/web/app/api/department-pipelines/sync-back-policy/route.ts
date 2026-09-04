import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

export async function PUT(request: NextRequest) {
  return proxyToFastApi(request, "/api/department-pipelines/sync-back-policy", {
    method: "PUT",
    body: await request.text(),
  })
}
