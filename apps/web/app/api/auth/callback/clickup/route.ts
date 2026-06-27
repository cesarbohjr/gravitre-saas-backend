import { NextRequest } from "next/server"

import { forwardClickupOAuthCallback } from "@/lib/clickup-oauth-callback"

/**
 * ClickUp OAuth redirect — shorter path when ClickUp accepts a path-based callback.
 * Domain-only callbacks land on / and are handled in proxy.ts.
 */
export async function GET(request: NextRequest) {
  return forwardClickupOAuthCallback(request)
}
