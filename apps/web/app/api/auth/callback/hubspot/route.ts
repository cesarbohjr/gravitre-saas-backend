import { NextRequest } from "next/server"

import { completeConnectorOAuthCallback } from "@/lib/connector-oauth-callback"

/**
 * HubSpot apps may register gravitre.app/api/auth/callback/hubspot as the redirect URL.
 * Both this alias and /api/connectors/oauth/hubspot/callback must be listed in the HubSpot app.
 */
export async function GET(request: NextRequest) {
  return completeConnectorOAuthCallback(request, "hubspot")
}
