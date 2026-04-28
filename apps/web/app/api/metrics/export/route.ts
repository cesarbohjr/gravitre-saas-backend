import { NextRequest, NextResponse } from "next/server"

function getFastApiBaseUrl() {
  const value = process.env.FASTAPI_BASE_URL?.trim()
  if (!value) {
    throw new Error("FASTAPI_BASE_URL is not set")
  }
  return value.replace(/\/+$/, "")
}

export async function GET(request: NextRequest) {
  try {
    const baseUrl = getFastApiBaseUrl()
    const targetUrl = new URL(`${baseUrl}/api/metrics/export`)
    request.nextUrl.searchParams.forEach((value, key) => {
      targetUrl.searchParams.set(key, value)
    })

    const headers = new Headers()
    const auth = request.headers.get("authorization")
    const xOrgId = request.headers.get("x-org-id")
    const xEnv = request.headers.get("x-environment")
    if (auth) headers.set("authorization", auth)
    if (xOrgId) headers.set("x-org-id", xOrgId)
    if (xEnv) headers.set("x-environment", xEnv)

    const upstream = await fetch(targetUrl.toString(), {
      method: "GET",
      headers,
      cache: "no-store",
    })
    if (!upstream.ok) {
      const detail = await upstream.text()
      return NextResponse.json(
        { error: "Failed to export metrics", detail: detail || upstream.statusText },
        { status: upstream.status }
      )
    }

    const csv = await upstream.text()
    return new NextResponse(csv, {
      status: 200,
      headers: {
        "content-type": "text/csv; charset=utf-8",
        "content-disposition": `attachment; filename="gravitre-metrics.csv"`,
      },
    })
  } catch (error) {
    return NextResponse.json(
      {
        error: "Export unavailable",
        detail: error instanceof Error ? error.message : "Unknown export error",
      },
      { status: 500 }
    )
  }
}
