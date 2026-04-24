import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

/** GET/POST /api/v1/operators/:id/links */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const search = request.nextUrl.search;
  return proxyApiToBackend(request, `/api/v1/operators/${id}/links${search}`);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.text();
  return proxyApiToBackend(request, `/api/v1/operators/${id}/links`, {
    method: "POST",
    body,
  });
}
