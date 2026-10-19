import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

// Settings > API keys lives in FastAPI (backend/app/routers/settings_api_keys.py):
// it hashes new secrets, stores scope and expiry, enforces the admin role and
// writes the audit trail. Rotate (/api/settings/api-keys/:id/rotate) has no
// route here and reaches FastAPI through the /api fallback rewrite.
export async function GET(request: NextRequest) {
  return proxyToFastApi(request, "/api/settings/api-keys")
}

export async function POST(request: NextRequest) {
  return proxyToFastApi(request, "/api/settings/api-keys")
}

export async function PATCH(request: NextRequest) {
  return proxyToFastApi(request, "/api/settings/api-keys")
}
