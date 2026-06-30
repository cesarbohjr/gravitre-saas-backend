import { NextResponse } from "next/server"

const REDACTED_PREFIXES = ["/api/internal", "/api/admin"]

function shouldRedactPath(path: string): boolean {
  return REDACTED_PREFIXES.some((prefix) => path.startsWith(prefix))
}

function redactOpenApi(spec: Record<string, unknown>): Record<string, unknown> {
  const paths = (spec.paths ?? {}) as Record<string, unknown>
  const filteredPaths: Record<string, unknown> = {}

  for (const [path, value] of Object.entries(paths)) {
    if (!shouldRedactPath(path)) {
      filteredPaths[path] = value
    }
  }

  return {
    ...spec,
    paths: filteredPaths,
    info: {
      ...(typeof spec.info === "object" && spec.info ? spec.info : {}),
      title: "Gravitre Public API",
      description:
        "Customer-facing REST API. Internal and admin routes are omitted from this export.",
    },
  }
}

export async function GET() {
  const backendUrl = (process.env.FASTAPI_BASE_URL || "http://localhost:8000")
    .trim()
    .replace(/\/+$/, "")

  try {
    const response = await fetch(`${backendUrl}/openapi.json`, {
      next: { revalidate: 3600 },
    })

    if (!response.ok) {
      return NextResponse.json(
        { error: "Failed to fetch OpenAPI specification from backend" },
        { status: 502 },
      )
    }

    const spec = (await response.json()) as Record<string, unknown>
    const redacted = redactOpenApi(spec)

    return NextResponse.json(redacted, {
      headers: {
        "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
      },
    })
  } catch {
    return NextResponse.json(
      { error: "OpenAPI specification unavailable" },
      { status: 503 },
    )
  }
}
