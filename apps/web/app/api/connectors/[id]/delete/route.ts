import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

interface RouteParams {
  params: Promise<{ id: string }>
}

/** Proxies frontend POST /delete to backend DELETE /{id} with confirm body. */
export async function POST(request: NextRequest, { params }: RouteParams) {
  const { id } = await params
  const body = await request.text()
  const headers = new Headers()
  const auth = request.headers.get("authorization")
  const contentType = request.headers.get("content-type")
  const accept = request.headers.get("accept")
  const xOrgId = request.headers.get("x-org-id")
  const xEnv = request.headers.get("x-environment")

  if (auth) headers.set("authorization", auth)
  headers.set("content-type", contentType || "application/json")
  if (accept) headers.set("accept", accept)
  if (xOrgId) headers.set("x-org-id", xOrgId)
  if (xEnv) headers.set("x-environment", xEnv)

  const baseUrl = process.env.FASTAPI_BASE_URL?.trim()?.replace(/\/+$/, "")
  if (!baseUrl) {
    return new Response(
      JSON.stringify({ error: "Server configuration error", detail: "FASTAPI_BASE_URL is not set" }),
      { status: 500, headers: { "content-type": "application/json" } }
    )
  }

  const url = new URL(`${baseUrl}/api/connectors/${id}`)
  request.nextUrl.searchParams.forEach((value, key) => {
    url.searchParams.set(key, value)
  })

  try {
    const upstream = await fetch(url.toString(), {
      method: "DELETE",
      headers,
      body: body || undefined,
      cache: "no-store",
    })
    const contentTypeHeader = upstream.headers.get("content-type") ?? ""
    const payload = contentTypeHeader.includes("application/json")
      ? await upstream.json()
      : { detail: await upstream.text() }
    return new Response(JSON.stringify(payload), {
      status: upstream.status,
      headers: { "content-type": "application/json; charset=utf-8" },
    })
  } catch (error) {
    return new Response(
      JSON.stringify({
        error: "Backend request failed",
        detail: error instanceof Error ? error.message : "Unknown proxy error",
      }),
      { status: 502, headers: { "content-type": "application/json" } }
    )
  }
}
