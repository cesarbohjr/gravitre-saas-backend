import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
import {
  addInstruction,
  addTrainingDataset,
  addTrainingJob,
  getDemoStore,
} from "@/lib/demo-runtime-store"

interface RouteParams {
  params: Promise<{ path: string[] }>
}

function buildTarget(path: string[] | undefined): string {
  const segments = path ?? []
  const suffix = segments.length > 0 ? `/${segments.join("/")}` : ""
  return `/api/training${suffix}`
}

function isProxyEnabled(): boolean {
  return Boolean(process.env.FASTAPI_BASE_URL?.trim())
}

async function maybeProxy(request: NextRequest, target: string) {
  if (!isProxyEnabled()) return null
  const upstream = await proxyToFastApi(request, target)
  if (upstream.ok || upstream.status < 500) return upstream
  return null
}

function getPath(path: string[] | undefined): string[] {
  return (path ?? []).filter(Boolean)
}

async function readJson(request: NextRequest): Promise<Record<string, unknown>> {
  return (await request.json().catch(() => ({}))) as Record<string, unknown>
}

export async function GET(request: NextRequest, { params }: RouteParams) {
  const { path } = await params
  const target = buildTarget(path)
  const proxied = await maybeProxy(request, target)
  if (proxied) return proxied

  const parts = getPath(path)
  const store = getDemoStore().training

  if (parts[0] === "datasets") {
    if (parts.length === 1) return NextResponse.json({ datasets: store.datasets })
    const dataset = store.datasets.find((item) => item.id === parts[1])
    return dataset
      ? NextResponse.json(dataset)
      : NextResponse.json({ detail: "Dataset not found" }, { status: 404 })
  }

  if (parts[0] === "jobs") {
    if (parts.length === 1) return NextResponse.json({ jobs: store.jobs })
    const job = store.jobs.find((item) => item.id === parts[1])
    return job ? NextResponse.json(job) : NextResponse.json({ detail: "Job not found" }, { status: 404 })
  }

  if (parts[0] === "instructions") {
    if (parts.length === 1) return NextResponse.json({ instructions: store.instructions })
    const instruction = store.instructions.find((item) => item.id === parts[1])
    return instruction
      ? NextResponse.json(instruction)
      : NextResponse.json({ detail: "Instruction not found" }, { status: 404 })
  }

  return NextResponse.json({ detail: "Unsupported training path" }, { status: 404 })
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  const { path } = await params
  const target = buildTarget(path)
  const proxied = await maybeProxy(request, target)
  if (proxied) return proxied

  const parts = getPath(path)
  const body = await readJson(request)
  const store = getDemoStore().training

  if (parts[0] === "datasets" && parts.length === 1) {
    const name = String(body.name ?? "").trim()
    const type = String(body.type ?? "examples")
    if (!name) return NextResponse.json({ detail: "name is required" }, { status: 400 })
    if (type !== "examples" && type !== "documents" && type !== "feedback") {
      return NextResponse.json({ detail: "invalid type" }, { status: 400 })
    }
    return NextResponse.json(
      addTrainingDataset({ name, type, description: body.description ? String(body.description) : undefined }),
      { status: 201 }
    )
  }

  if (parts[0] === "datasets" && parts[2] === "records") {
    const dataset = store.datasets.find((item) => item.id === parts[1])
    if (!dataset) return NextResponse.json({ detail: "Dataset not found" }, { status: 404 })
    const records = Array.isArray(body.records) ? body.records : []
    const added = records.length
    dataset.record_count += added
    dataset.updated_at = new Date().toISOString()
    return NextResponse.json({ added })
  }

  if (parts[0] === "jobs" && parts.length === 1) {
    const datasetId = String(body.dataset_id ?? "")
    const modelBase = String(body.model_base ?? "meson-base-v1")
    if (!datasetId) return NextResponse.json({ detail: "dataset_id is required" }, { status: 400 })
    if (!store.datasets.some((item) => item.id === datasetId)) {
      return NextResponse.json({ detail: "Dataset not found" }, { status: 404 })
    }
    return NextResponse.json(addTrainingJob(datasetId, modelBase), { status: 201 })
  }

  if (parts[0] === "jobs" && parts[2] === "cancel") {
    const job = store.jobs.find((item) => item.id === parts[1])
    if (!job) return NextResponse.json({ detail: "Job not found" }, { status: 404 })
    job.status = "cancelled"
    job.updated_at = new Date().toISOString()
    return NextResponse.json({ ok: true })
  }

  if (parts[0] === "instructions" && parts.length === 1) {
    const name = String(body.name ?? "").trim()
    const content = String(body.content ?? "").trim()
    if (!name || !content) {
      return NextResponse.json({ detail: "name and content are required" }, { status: 400 })
    }
    return NextResponse.json(
      addInstruction({
        name,
        content,
        agent_id: body.agent_id ? String(body.agent_id) : undefined,
      }),
      { status: 201 }
    )
  }

  return NextResponse.json({ detail: "Unsupported training path" }, { status: 404 })
}

export async function PATCH(request: NextRequest, { params }: RouteParams) {
  const { path } = await params
  const target = buildTarget(path)
  const proxied = await maybeProxy(request, target)
  if (proxied) return proxied

  const parts = getPath(path)
  const body = await readJson(request)
  const store = getDemoStore().training

  if (parts[0] === "instructions" && parts[1]) {
    const instruction = store.instructions.find((item) => item.id === parts[1])
    if (!instruction) return NextResponse.json({ detail: "Instruction not found" }, { status: 404 })
    if (body.name !== undefined) instruction.name = String(body.name)
    if (body.content !== undefined) instruction.content = String(body.content)
    if (body.is_active !== undefined) instruction.is_active = Boolean(body.is_active)
    instruction.updated_at = new Date().toISOString()
    return NextResponse.json(instruction)
  }

  return NextResponse.json({ detail: "Unsupported training path" }, { status: 404 })
}

export async function DELETE(request: NextRequest, { params }: RouteParams) {
  const { path } = await params
  const target = buildTarget(path)
  const proxied = await maybeProxy(request, target)
  if (proxied) return proxied

  const parts = getPath(path)
  const store = getDemoStore().training

  if (parts[0] === "datasets" && parts[1]) {
    const before = store.datasets.length
    store.datasets = store.datasets.filter((item) => item.id !== parts[1])
    store.jobs = store.jobs.filter((item) => item.dataset_id !== parts[1])
    if (store.datasets.length === before) {
      return NextResponse.json({ detail: "Dataset not found" }, { status: 404 })
    }
    return new NextResponse(null, { status: 204 })
  }

  if (parts[0] === "instructions" && parts[1]) {
    const before = store.instructions.length
    store.instructions = store.instructions.filter((item) => item.id !== parts[1])
    if (store.instructions.length === before) {
      return NextResponse.json({ detail: "Instruction not found" }, { status: 404 })
    }
    return new NextResponse(null, { status: 204 })
  }

  return NextResponse.json({ detail: "Unsupported training path" }, { status: 404 })
}
