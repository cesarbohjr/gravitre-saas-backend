import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"

type RagResult = {
  content: string
  score: number
  source: string
}

function isMissingRelationError(message: string | undefined) {
  const value = String(message ?? "").toLowerCase()
  return value.includes("does not exist") || value.includes("relation")
}

function normalizeQueryInput(value: unknown) {
  return String(value ?? "").trim()
}

function scoreContent(content: string, query: string): number {
  const normalizedContent = content.toLowerCase()
  const normalizedQuery = query.toLowerCase()
  if (!normalizedContent || !normalizedQuery) return 0
  if (normalizedContent === normalizedQuery) return 1
  if (normalizedContent.startsWith(normalizedQuery)) return 0.95
  if (normalizedContent.includes(normalizedQuery)) return 0.9

  const queryTerms = normalizedQuery.split(/\s+/).filter(Boolean)
  if (queryTerms.length === 0) return 0
  const matches = queryTerms.reduce((acc, term) => (normalizedContent.includes(term) ? acc + 1 : acc), 0)
  const ratio = matches / queryTerms.length
  return Number((0.4 + ratio * 0.5).toFixed(4))
}

async function callFastApiRag(request: NextRequest, orgId: string): Promise<NextResponse | null> {
  const base = process.env.FASTAPI_BASE_URL?.trim()
  if (!base) return null

  const upstreamUrl = new URL(`${base.replace(/\/+$/, "")}/api/rag`)
  request.nextUrl.searchParams.forEach((value, key) => {
    upstreamUrl.searchParams.set(key, value)
  })

  const auth = request.headers.get("authorization")
  const xOrgId = request.headers.get("x-org-id") ?? orgId
  const contentType = request.headers.get("content-type")
  const headers = new Headers()
  if (auth) headers.set("authorization", auth)
  if (xOrgId) headers.set("x-org-id", xOrgId)
  if (contentType) headers.set("content-type", contentType)
  headers.set("accept", "application/json")

  const method = request.method.toUpperCase()
  const init: RequestInit = {
    method,
    headers,
    cache: "no-store",
  }

  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const body = await request.text()
    if (body) init.body = body
  }

  try {
    const upstreamResponse = await fetch(upstreamUrl.toString(), init)
    const payload = await upstreamResponse
      .json()
      .catch(() => null)

    if (!upstreamResponse.ok) {
      return null
    }

    if (payload && Array.isArray(payload.results)) {
      return NextResponse.json({
        results: payload.results.map((row: Record<string, unknown>) => ({
          content: String(row.content ?? ""),
          score: Number(row.score ?? 0) || 0,
          source: String(row.source ?? row.source_title ?? "unknown"),
        })),
      })
    }

    if (Array.isArray(payload)) {
      return NextResponse.json({
        results: payload.map((row: Record<string, unknown>) => ({
          content: String(row.content ?? ""),
          score: Number(row.score ?? 0) || 0,
          source: String(row.source ?? row.source_title ?? "unknown"),
        })),
      })
    }

    return NextResponse.json({ results: [] })
  } catch {
    return null
  }
}

async function fallbackSupabaseRagSearch(
  request: NextRequest,
  supabase: ReturnType<typeof createSupabaseRouteClient>,
  orgId: string
) {
  const requestBody =
    request.method.toUpperCase() === "GET"
      ? {}
      : await request.json().catch(() => ({}))
  const query =
    normalizeQueryInput(request.nextUrl.searchParams.get("q")) ||
    normalizeQueryInput((requestBody as Record<string, unknown>).query) ||
    normalizeQueryInput((requestBody as Record<string, unknown>).text)

  if (!query) {
    return NextResponse.json({ results: [] })
  }

  const sourceFilter = normalizeQueryInput(
    request.nextUrl.searchParams.get("sourceId") ||
      (requestBody as Record<string, unknown>).sourceId
  )

  let chunksQuery = supabase
    .from("rag_chunks")
    .select("content, source_id")
    .eq("org_id", orgId)
    .ilike("content", `%${query}%`)
    .limit(50)

  if (sourceFilter) {
    chunksQuery = chunksQuery.eq("source_id", sourceFilter)
  }

  const { data: chunks, error: chunksError } = await chunksQuery
  if (chunksError) {
    if (isMissingRelationError(chunksError.message)) {
      return NextResponse.json({ results: [] })
    }
    return NextResponse.json({ error: chunksError.message }, { status: 500 })
  }

  const sourceIds = Array.from(new Set((chunks ?? []).map((chunk) => chunk.source_id).filter(Boolean)))
  let sourceNameMap: Record<string, string> = {}
  if (sourceIds.length > 0) {
    const { data: sources, error: sourceError } = await supabase
      .from("rag_sources")
      .select("id, title")
      .eq("org_id", orgId)
      .in("id", sourceIds)

    if (sourceError && !isMissingRelationError(sourceError.message)) {
      return NextResponse.json({ error: sourceError.message }, { status: 500 })
    }

    sourceNameMap = Object.fromEntries(
      (sources ?? []).map((source) => [String(source.id), String(source.title ?? "unknown")])
    )
  }

  const scoredResults: RagResult[] = (chunks ?? [])
    .map((chunk) => ({
      content: String(chunk.content ?? ""),
      score: scoreContent(String(chunk.content ?? ""), query),
      source: sourceNameMap[String(chunk.source_id)] ?? "unknown",
    }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 20)

  return NextResponse.json({ results: scoredResults })
}

export async function GET(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const proxyResponse = await callFastApiRag(request, orgId)
    if (proxyResponse) {
      return proxyResponse
    }
    return await fallbackSupabaseRagSearch(request, supabase, orgId)
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const proxyResponse = await callFastApiRag(request, orgId)
    if (proxyResponse) {
      return proxyResponse
    }
    return await fallbackSupabaseRagSearch(request, supabase, orgId)
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
