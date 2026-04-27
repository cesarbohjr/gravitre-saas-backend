import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"

type SourceBackend = "sources" | "rag_sources"

type SourceModel = {
  id: string
  name: string
  type: string
  status: string
  lastSync: string | null
  recordCount: number
}

function isMissingRelationError(message: string | undefined) {
  const value = String(message ?? "").toLowerCase()
  return value.includes("does not exist") || value.includes("relation")
}

function normalizeStatus(value: unknown) {
  const status = String(value ?? "connected").trim().toLowerCase()
  if (["connected", "syncing", "error", "disconnected", "pending"].includes(status)) {
    return status
  }
  return "connected"
}

function toIsoOrNull(value: unknown): string | null {
  if (!value) return null
  const date = new Date(String(value))
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

async function detectSourceBackend(
  supabase: ReturnType<typeof createSupabaseRouteClient>,
  orgId: string
): Promise<{ backend: SourceBackend | null; error?: string }> {
  const sourcesProbe = await supabase
    .from("sources")
    .select("id", { count: "exact", head: true })
    .eq("org_id", orgId)

  if (!sourcesProbe.error) {
    return { backend: "sources" }
  }

  if (!isMissingRelationError(sourcesProbe.error.message)) {
    return { backend: null, error: sourcesProbe.error.message }
  }

  const ragProbe = await supabase
    .from("rag_sources")
    .select("id", { count: "exact", head: true })
    .eq("org_id", orgId)

  if (!ragProbe.error) {
    return { backend: "rag_sources" }
  }

  if (!isMissingRelationError(ragProbe.error.message)) {
    return { backend: null, error: ragProbe.error.message }
  }

  return { backend: null }
}

async function getSourcesFromSourcesTable(
  supabase: ReturnType<typeof createSupabaseRouteClient>,
  orgId: string
) {
  const { data, error } = await supabase
    .from("sources")
    .select("*")
    .eq("org_id", orgId)
    .order("created_at", { ascending: false })
    .limit(200)

  if (error) {
    return { error: error.message, sources: [] as SourceModel[] }
  }

  const sources = (data ?? []).map((row) => {
    const metadata = (row.metadata ?? {}) as Record<string, unknown>
    const recordCount = Number(
      row.record_count ?? row.records_count ?? row.tables_count ?? metadata.recordCount ?? 0
    )
    return {
      id: String(row.id),
      name: String(row.name ?? row.title ?? "Source"),
      type: String(row.type ?? "unknown"),
      status: normalizeStatus(row.status),
      lastSync: toIsoOrNull(row.last_sync_at ?? row.updated_at ?? row.created_at),
      recordCount: Number.isFinite(recordCount) ? recordCount : 0,
    } satisfies SourceModel
  })

  return { sources, error: null }
}

async function getSourcesFromRagTables(
  supabase: ReturnType<typeof createSupabaseRouteClient>,
  orgId: string
) {
  const { data: ragSources, error: ragSourcesError } = await supabase
    .from("rag_sources")
    .select("id, title, type, metadata, created_at, updated_at")
    .eq("org_id", orgId)
    .order("created_at", { ascending: false })
    .limit(200)

  if (ragSourcesError) {
    return { error: ragSourcesError.message, sources: [] as SourceModel[] }
  }

  const sourceIds = (ragSources ?? []).map((source) => source.id)
  let countsBySourceId: Record<string, number> = {}
  if (sourceIds.length > 0) {
    const { data: docs, error: docsError } = await supabase
      .from("rag_documents")
      .select("source_id")
      .eq("org_id", orgId)
      .in("source_id", sourceIds)
      .limit(10000)

    if (docsError) {
      return { error: docsError.message, sources: [] as SourceModel[] }
    }

    countsBySourceId = (docs ?? []).reduce<Record<string, number>>((acc, doc) => {
      const key = String(doc.source_id)
      acc[key] = (acc[key] ?? 0) + 1
      return acc
    }, {})
  }

  const sources = (ragSources ?? []).map((source) => {
    const metadata = (source.metadata ?? {}) as Record<string, unknown>
    const status = normalizeStatus(metadata.status ?? "connected")
    const metaRecordCount = Number(metadata.recordCount ?? metadata.recordsCount ?? 0)
    return {
      id: String(source.id),
      name: String(source.title ?? "Source"),
      type: String(source.type ?? "unknown"),
      status,
      lastSync: toIsoOrNull(metadata.lastSync ?? source.updated_at ?? source.created_at),
      recordCount:
        Number.isFinite(metaRecordCount) && metaRecordCount > 0
          ? metaRecordCount
          : countsBySourceId[String(source.id)] ?? 0,
    } satisfies SourceModel
  })

  return { sources, error: null }
}

export async function GET(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const backendResult = await detectSourceBackend(supabase, orgId)
    if (backendResult.error) {
      return NextResponse.json({ error: backendResult.error }, { status: 500 })
    }

    if (backendResult.backend === "sources") {
      const { sources, error } = await getSourcesFromSourcesTable(supabase, orgId)
      if (error) {
        return NextResponse.json({ error }, { status: 500 })
      }
      return NextResponse.json({ sources })
    }

    if (backendResult.backend === "rag_sources") {
      const { sources, error } = await getSourcesFromRagTables(supabase, orgId)
      if (error) {
        return NextResponse.json({ error }, { status: 500 })
      }
      return NextResponse.json({ sources })
    }

    return NextResponse.json({ sources: [] })
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

    const body = await request.json().catch(() => ({}))
    const name = String(body?.name ?? "").trim()
    const type = String(body?.type ?? "").trim().toLowerCase()
    if (!name || !type) {
      return NextResponse.json({ error: "name and type are required" }, { status: 400 })
    }

    const backendResult = await detectSourceBackend(supabase, orgId)
    if (backendResult.error) {
      return NextResponse.json({ error: backendResult.error }, { status: 500 })
    }

    if (backendResult.backend === "sources") {
      const { data, error } = await supabase
        .from("sources")
        .insert({
          org_id: orgId,
          name,
          type,
          status: normalizeStatus(body?.status),
        })
        .select("*")
        .single()

      if (error) {
        return NextResponse.json({ error: error.message }, { status: 500 })
      }

      const metadata = (data.metadata ?? {}) as Record<string, unknown>
      const source: SourceModel = {
        id: String(data.id),
        name: String(data.name ?? name),
        type: String(data.type ?? type),
        status: normalizeStatus(data.status),
        lastSync: toIsoOrNull(data.last_sync_at ?? data.updated_at ?? data.created_at),
        recordCount: Number(data.record_count ?? data.records_count ?? data.tables_count ?? metadata.recordCount ?? 0) || 0,
      }

      return NextResponse.json({ source }, { status: 201 })
    }

    if (backendResult.backend === "rag_sources") {
      const metadata = {
        status: normalizeStatus(body?.status),
        recordCount: Number(body?.recordCount ?? 0) || 0,
        lastSync: toIsoOrNull(body?.lastSync),
      }
      const { data, error } = await supabase
        .from("rag_sources")
        .insert({
          org_id: orgId,
          title: name,
          type,
          metadata,
        })
        .select("id, title, type, metadata, created_at, updated_at")
        .single()

      if (error) {
        return NextResponse.json({ error: error.message }, { status: 500 })
      }

      const sourceMeta = (data.metadata ?? {}) as Record<string, unknown>
      const source: SourceModel = {
        id: String(data.id),
        name: String(data.title ?? name),
        type: String(data.type ?? type),
        status: normalizeStatus(sourceMeta.status),
        lastSync: toIsoOrNull(sourceMeta.lastSync ?? data.updated_at ?? data.created_at),
        recordCount: Number(sourceMeta.recordCount ?? 0) || 0,
      }

      return NextResponse.json({ source }, { status: 201 })
    }

    return NextResponse.json({ error: "No sources backend table found" }, { status: 500 })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const body = await request.json().catch(() => ({}))
    const id = String(body?.id ?? "").trim()
    if (!id) {
      return NextResponse.json({ error: "id is required" }, { status: 400 })
    }

    const backendResult = await detectSourceBackend(supabase, orgId)
    if (backendResult.error) {
      return NextResponse.json({ error: backendResult.error }, { status: 500 })
    }

    if (backendResult.backend === "sources") {
      const updates: Record<string, unknown> = {}
      if (body?.name !== undefined) updates.name = String(body.name)
      if (body?.type !== undefined) updates.type = String(body.type)
      if (body?.status !== undefined) updates.status = normalizeStatus(body.status)
      if (Object.keys(updates).length === 0) {
        return NextResponse.json({ error: "No updatable fields provided" }, { status: 400 })
      }

      const { data, error } = await supabase
        .from("sources")
        .update(updates)
        .eq("org_id", orgId)
        .eq("id", id)
        .select("*")
        .single()

      if (error) {
        return NextResponse.json({ error: error.message }, { status: 500 })
      }

      const metadata = (data.metadata ?? {}) as Record<string, unknown>
      const source: SourceModel = {
        id: String(data.id),
        name: String(data.name ?? "Source"),
        type: String(data.type ?? "unknown"),
        status: normalizeStatus(data.status),
        lastSync: toIsoOrNull(data.last_sync_at ?? data.updated_at ?? data.created_at),
        recordCount: Number(data.record_count ?? data.records_count ?? data.tables_count ?? metadata.recordCount ?? 0) || 0,
      }
      return NextResponse.json({ source })
    }

    if (backendResult.backend === "rag_sources") {
      const { data: existing, error: existingError } = await supabase
        .from("rag_sources")
        .select("metadata")
        .eq("org_id", orgId)
        .eq("id", id)
        .single()

      if (existingError) {
        return NextResponse.json({ error: existingError.message }, { status: 500 })
      }

      const existingMetadata = (existing?.metadata ?? {}) as Record<string, unknown>
      const mergedMetadata = {
        ...existingMetadata,
        ...(body?.status !== undefined ? { status: normalizeStatus(body.status) } : {}),
        ...(body?.recordCount !== undefined
          ? { recordCount: Number(body.recordCount) || 0 }
          : {}),
        ...(body?.lastSync !== undefined ? { lastSync: toIsoOrNull(body.lastSync) } : {}),
      }

      const updates: Record<string, unknown> = { metadata: mergedMetadata }
      if (body?.name !== undefined) updates.title = String(body.name)
      if (body?.type !== undefined) updates.type = String(body.type)

      const { data, error } = await supabase
        .from("rag_sources")
        .update(updates)
        .eq("org_id", orgId)
        .eq("id", id)
        .select("id, title, type, metadata, created_at, updated_at")
        .single()

      if (error) {
        return NextResponse.json({ error: error.message }, { status: 500 })
      }

      const sourceMetadata = (data.metadata ?? {}) as Record<string, unknown>
      const source: SourceModel = {
        id: String(data.id),
        name: String(data.title ?? "Source"),
        type: String(data.type ?? "unknown"),
        status: normalizeStatus(sourceMetadata.status),
        lastSync: toIsoOrNull(sourceMetadata.lastSync ?? data.updated_at ?? data.created_at),
        recordCount: Number(sourceMetadata.recordCount ?? 0) || 0,
      }
      return NextResponse.json({ source })
    }

    return NextResponse.json({ error: "No sources backend table found" }, { status: 500 })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const body = await request.json().catch(() => ({}))
    const id = String(body?.id ?? "").trim()
    if (!id) {
      return NextResponse.json({ error: "id is required" }, { status: 400 })
    }

    const backendResult = await detectSourceBackend(supabase, orgId)
    if (backendResult.error) {
      return NextResponse.json({ error: backendResult.error }, { status: 500 })
    }

    if (backendResult.backend === "sources") {
      const { error } = await supabase.from("sources").delete().eq("org_id", orgId).eq("id", id)
      if (error) {
        return NextResponse.json({ error: error.message }, { status: 500 })
      }
      return NextResponse.json({ success: true })
    }

    if (backendResult.backend === "rag_sources") {
      const { error } = await supabase.from("rag_sources").delete().eq("org_id", orgId).eq("id", id)
      if (error) {
        return NextResponse.json({ error: error.message }, { status: 500 })
      }
      return NextResponse.json({ success: true })
    }

    return NextResponse.json({ error: "No sources backend table found" }, { status: 500 })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
