import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
import { hasIntelligenceBackend } from "@/lib/admin-intelligence"

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" } as const

/**
 * Promote or reject a candidate memory. This is a real mutation, so it only
 * works against the configured backend. When no backend is wired up we return
 * 503 with a clear message rather than pretending the action succeeded.
 */
export async function POST(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params

  if (!hasIntelligenceBackend()) {
    return new NextResponse(
      JSON.stringify({
        error: "Promotion backend not configured",
        detail:
          "Memory promotion writes require the intelligence backend (FASTAPI_BASE_URL) to be connected.",
      }),
      { status: 503, headers: JSON_HEADERS },
    )
  }

  return proxyToFastApi(request, `/api/admin/intelligence/memory-promotion/${encodeURIComponent(id)}`)
}
