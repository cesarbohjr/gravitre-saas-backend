import { NextRequest } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

interface RouteParams {
  params: Promise<{ path: string[] }>
}

function buildTarget(path: string[] | undefined): string {
  const segments = path ?? []
  const suffix = segments.length > 0 ? `/${segments.join("/")}` : ""
  return `/api/training${suffix}`
}

export async function GET(request: NextRequest, { params }: RouteParams) {
  const { path } = await params
  return proxyToFastApi(request, buildTarget(path))
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  const { path } = await params
  return proxyToFastApi(request, buildTarget(path))
}

export async function PATCH(request: NextRequest, { params }: RouteParams) {
  const { path } = await params
  return proxyToFastApi(request, buildTarget(path))
}

export async function DELETE(request: NextRequest, { params }: RouteParams) {
  const { path } = await params
  return proxyToFastApi(request, buildTarget(path))
}
