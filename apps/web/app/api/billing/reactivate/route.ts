import { NextRequest } from "next/server"
import { proxyAuthenticatedBillingPost } from "@/lib/billing-route-proxy"

export async function POST(request: NextRequest) {
  return proxyAuthenticatedBillingPost(request, "/api/billing/reactivate")
}
